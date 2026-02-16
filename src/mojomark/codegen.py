"""Version-aware Mojo benchmark code generation.

Renders benchmark templates into version-specific ``.mojo`` source files.
Each template contains the algorithm in a version-neutral format with
``{{TOKEN}}`` markers for API differences and ``{{#MODERN}}``/``{{#LEGACY}}``
conditional blocks for structural differences.

The renderer applies a version profile and wraps the workload in the
appropriate timing harness:

* **modern** (>=0.26): ``benchmark.run[]`` with ``keep()``/``black_box()``
* **transitional** (0.25.x): ``time.now()`` with modern collection types
* **legacy** (<0.25): ``time.now()`` with legacy types (``DynamicVector``)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"

# ---------------------------------------------------------------------------
# Version profiles — ordered from most specific to least specific.
# get_profile() returns the first whose min_version <= target.
# ---------------------------------------------------------------------------

VERSION_PROFILES: list[dict] = [
    {
        "name": "modern",
        "min_version": (0, 26),
        "tokens": {
            "LIST": "List",
            "APPEND": "append",
            "CONST": "comptime",
            "MUT": "mut",
            "STRUCT_DECORATOR": "@fieldwise_init",
            "STRUCT_TRAITS": "Copyable, Movable",
            "MOVE_SUFFIX": "^",
        },
        "harness": "benchmark_module",
        "conditional": "MODERN",
    },
    {
        "name": "transitional",
        "min_version": (0, 25),
        "tokens": {
            "LIST": "List",
            "APPEND": "append",
            "CONST": "alias",
            "MUT": "inout",
            "STRUCT_DECORATOR": "",
            "STRUCT_TRAITS": "CollectionElement",
            "MOVE_SUFFIX": "",
        },
        "harness": "manual_timing",
        "conditional": "LEGACY",
    },
    {
        "name": "legacy",
        "min_version": (0, 0),
        "tokens": {
            "LIST": "DynamicVector",
            "APPEND": "push_back",
            "CONST": "alias",
            "MUT": "inout",
            "STRUCT_DECORATOR": "",
            "STRUCT_TRAITS": "CollectionElement",
            "MOVE_SUFFIX": "",
        },
        "harness": "manual_timing",
        "conditional": "LEGACY",
    },
]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def parse_version_tuple(version_str: str) -> tuple[int, ...]:
    """Parse ``'0.26.1'`` into ``(0, 26, 1)``."""
    parts: list[int] = []
    for p in version_str.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def get_profile(mojo_version: str) -> dict:
    """Select the best version profile for *mojo_version*."""
    ver = parse_version_tuple(mojo_version)
    for profile in VERSION_PROFILES:
        if ver >= profile["min_version"]:
            return profile
    return VERSION_PROFILES[-1]


# ---------------------------------------------------------------------------
# Template parsing
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(r"^#\s*==(\w+)==\s*$")
_IMPORT_RE = re.compile(r"^#\s*IMPORT:\s*(.+)$")
_KEEP_RE = re.compile(r"^#\s*KEEP:\s*(\w+)\s*(\w+)?\s*$")
_COND_BLOCK_RE = re.compile(
    r"\{\{#(MODERN|LEGACY)\}\}\n?(.*?)\{\{/\1\}\}\n?",
    re.DOTALL,
)


def _parse_template(text: str) -> dict:
    """Parse a template into its constituent sections.

    Returns a dict with keys:
        docstring, imports, module, setup, workload, keeps
    """
    docstring = ""
    body = text
    stripped = text.lstrip()
    if stripped.startswith('"""'):
        first = text.find('"""')
        second = text.find('"""', first + 3)
        if second != -1:
            docstring = text[: second + 3].strip()
            body = text[second + 3 :]

    sections: dict[str, list[str]] = {
        "MODULE": [],
        "SETUP": [],
        "WORKLOAD": [],
    }
    imports: list[str] = []
    keeps: list[tuple[str, str]] = []
    current_section: str | None = None

    for line in body.splitlines():
        stripped_line = line.strip()

        m = _SECTION_RE.match(stripped_line)
        if m:
            current_section = m.group(1)
            continue

        m = _IMPORT_RE.match(stripped_line)
        if m:
            imports.append(m.group(1).strip())
            continue

        m = _KEEP_RE.match(stripped_line)
        if m:
            keeps.append((m.group(1), m.group(2) or "int"))
            continue

        if current_section and current_section in sections:
            sections[current_section].append(line)

    return {
        "docstring": docstring,
        "imports": imports,
        "module": "\n".join(sections["MODULE"]),
        "setup": "\n".join(sections["SETUP"]),
        "workload": "\n".join(sections["WORKLOAD"]),
        "keeps": keeps,
    }


# ---------------------------------------------------------------------------
# Token + conditional expansion
# ---------------------------------------------------------------------------


def _apply_tokens(text: str, tokens: dict[str, str]) -> str:
    """Replace ``{{TOKEN}}`` markers with profile values."""
    for key, val in tokens.items():
        text = text.replace("{{" + key + "}}", val)
    return text


def _apply_conditionals(text: str, keep_tag: str) -> str:
    """Keep ``{{#<keep_tag>}}`` blocks, remove the other."""

    def replacer(m: re.Match) -> str:
        tag = m.group(1)
        content = m.group(2)
        if tag == keep_tag:
            return content
        return ""

    prev = None
    while prev != text:
        prev = text
        text = _COND_BLOCK_RE.sub(replacer, text)

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _expand(text: str, profile: dict) -> str:
    """Apply token substitution and conditional blocks."""
    text = _apply_tokens(text, profile["tokens"])
    text = _apply_conditionals(text, profile["conditional"])
    return text


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------


def _indent(text: str, spaces: int) -> str:
    """Indent every non-empty line by *spaces*."""
    prefix = " " * spaces
    return "\n".join(prefix + line if line.strip() else "" for line in text.splitlines())


def _strip_blank_edges(text: str) -> str:
    """Strip leading/trailing blank lines (preserving internal structure)."""
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def _build_modern(parsed: dict, profile: dict) -> str:
    """Generate a ``.mojo`` file using the ``benchmark`` module harness."""
    parts: list[str] = []

    if parsed["docstring"]:
        parts.append(parsed["docstring"])
        parts.append("")

    needs_black_box = "black_box(" in parsed["workload"]
    parts.append("import benchmark")
    if needs_black_box:
        parts.append("from benchmark import keep, black_box")
    else:
        parts.append("from benchmark import keep")
    for imp in parsed["imports"]:
        parts.append(imp)
    parts.append("")

    module_code = _strip_blank_edges(_expand(parsed["module"], profile))
    if module_code:
        parts.append("")
        parts.append(module_code)
        parts.append("")

    parts.append("")
    parts.append("fn main() raises:")

    setup_code = _strip_blank_edges(_expand(parsed["setup"], profile))
    if setup_code:
        parts.append(_indent(setup_code, 4))
        parts.append("")

    parts.append("    fn workload() capturing:")
    workload_code = _strip_blank_edges(_expand(parsed["workload"], profile))
    parts.append(_indent(workload_code, 8))

    for varname, _ in parsed["keeps"]:
        parts.append(f"        keep({varname})")
    parts.append("")

    parts.append("    var report = benchmark.run[workload](2, 1_000_000_000, 0.1, 2)")
    parts.append('    print("MOJOMARK_NS", Int(report.mean("ns")))')
    parts.append("")

    return "\n".join(parts)


def _build_legacy(parsed: dict, profile: dict) -> str:
    """Generate a ``.mojo`` file using the ``time.now()`` manual harness."""
    parts: list[str] = []

    if parsed["docstring"]:
        parts.append(parsed["docstring"])
        parts.append("")

    parts.append("from time import now")
    for imp in parsed["imports"]:
        parts.append(imp)
    parts.append("")

    module_code = _strip_blank_edges(_expand(parsed["module"], profile))
    if module_code:
        parts.append("")
        parts.append(module_code)
        parts.append("")

    parts.append("")
    parts.append("fn main():")

    setup_code = _strip_blank_edges(_expand(parsed["setup"], profile))
    if setup_code:
        parts.append(_indent(setup_code, 4))
        parts.append("")

    parts.append("    var _bench_start = now()")
    parts.append("")

    workload_code = _strip_blank_edges(_expand(parsed["workload"], profile))
    parts.append(_indent(workload_code, 4))
    parts.append("")

    parts.append("    var _bench_elapsed = now() - _bench_start")
    parts.append("")

    _sentinel = {
        "int": "{var} == -1",
        "float": "{var} == -1.0",
        "str": "len({var}) == 0",
        "list": "{var}[0] == -1",
    }
    for varname, type_hint in parsed["keeps"]:
        pattern = _sentinel.get(type_hint, _sentinel["int"])
        parts.append(f"    if {pattern.format(var=varname)}:")
        parts.append('        print("unreachable")')
    parts.append("")

    parts.append('    print("MOJOMARK_NS", _bench_elapsed)')
    parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_template(template_path: Path, mojo_version: str) -> str:
    """Render a benchmark template for a specific Mojo version.

    Args:
        template_path: Path to the ``.mojo`` template file.
        mojo_version: Target Mojo version string (e.g. ``'0.26.1'``).

    Returns:
        Complete ``.mojo`` source code ready for compilation.
    """
    profile = get_profile(mojo_version)
    log.debug(
        "Rendering %s with profile %r for Mojo %s",
        template_path.name,
        profile["name"],
        mojo_version,
    )
    text = template_path.read_text()
    parsed = _parse_template(text)

    if profile["harness"] == "benchmark_module":
        return _build_modern(parsed, profile)
    return _build_legacy(parsed, profile)


def render_to_file(
    template_path: Path,
    output_dir: Path,
    mojo_version: str,
) -> Path:
    """Render a template and write the generated ``.mojo`` file.

    Args:
        template_path: Path to the template.
        output_dir: Directory to write the generated file.
        mojo_version: Target Mojo version.

    Returns:
        Path to the generated ``.mojo`` file.
    """
    source = render_template(template_path, mojo_version)
    output_path = output_dir / template_path.name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(source)
    return output_path


def discover_templates(
    templates_dir: Path = TEMPLATES_DIR,
    category: str | None = None,
) -> list[tuple[str, str, Path]]:
    """Discover benchmark templates.

    Returns:
        Sorted list of ``(name, category, template_path)`` tuples.
    """
    templates = []
    if not templates_dir.exists():
        return templates

    for template_file in sorted(templates_dir.rglob("*.mojo")):
        tmpl_category = template_file.parent.name
        tmpl_name = template_file.stem

        if category and tmpl_category != category:
            continue

        templates.append((tmpl_name, tmpl_category, template_file))

    return templates
