"""Tests for the version-aware benchmark code generation system."""

import tempfile
from pathlib import Path

from mojomark.codegen import (
    VERSION_PROFILES,
    _apply_conditionals,
    _apply_tokens,
    _parse_template,
    _strip_blank_edges,
    discover_templates,
    get_profile,
    parse_version_tuple,
    render_template,
    render_to_file,
)

# ---------------------------------------------------------------------------
# parse_version_tuple
# ---------------------------------------------------------------------------


class TestParseVersionTuple:
    def test_simple(self):
        assert parse_version_tuple("0.26.1") == (0, 26, 1)

    def test_four_parts(self):
        assert parse_version_tuple("0.26.1.0") == (0, 26, 1, 0)

    def test_single_part(self):
        assert parse_version_tuple("1") == (1,)

    def test_non_numeric_part(self):
        assert parse_version_tuple("0.7.beta") == (0, 7, 0)

    def test_empty_string(self):
        assert parse_version_tuple("") == (0,)


# ---------------------------------------------------------------------------
# get_profile
# ---------------------------------------------------------------------------


class TestGetProfile:
    def test_modern_version(self):
        profile = get_profile("0.26.1.0")
        assert profile["name"] == "modern"
        assert profile["tokens"]["LIST"] == "List"
        assert profile["harness"] == "benchmark_module"

    def test_legacy_version(self):
        profile = get_profile("0.7.0")
        assert profile["name"] == "legacy"
        assert profile["tokens"]["LIST"] == "DynamicVector"
        assert profile["harness"] == "manual_timing"

    def test_transitional_version(self):
        profile = get_profile("0.25.7.0")
        assert profile["name"] == "transitional"
        assert profile["tokens"]["LIST"] == "List"
        assert profile["tokens"]["CONST"] == "alias"
        assert profile["harness"] == "manual_timing"

    def test_very_old_version(self):
        profile = get_profile("0.1.0")
        assert profile["name"] == "legacy"

    def test_future_version(self):
        profile = get_profile("1.0.0")
        assert profile["name"] == "modern"

    def test_profiles_are_ordered_descending(self):
        versions = [p["min_version"] for p in VERSION_PROFILES]
        assert versions == sorted(versions, reverse=True)


# ---------------------------------------------------------------------------
# _parse_template
# ---------------------------------------------------------------------------


class TestParseTemplate:
    def test_extracts_docstring(self):
        text = '"""My doc."""\n\n# ==MODULE==\nfn foo(): pass\n'
        parsed = _parse_template(text)
        assert parsed["docstring"] == '"""My doc."""'

    def test_extracts_multiline_docstring(self):
        text = '"""Line1\nLine2\nLine3"""\n\n# ==MODULE==\ncode\n'
        parsed = _parse_template(text)
        assert "Line1" in parsed["docstring"]
        assert "Line3" in parsed["docstring"]

    def test_extracts_sections(self):
        text = (
            "# ==MODULE==\nfn helper(): pass\n"
            "# ==SETUP==\nvar x = 1\n"
            "# ==WORKLOAD==\nvar y = x + 1\n"
        )
        parsed = _parse_template(text)
        assert "fn helper(): pass" in parsed["module"]
        assert "var x = 1" in parsed["setup"]
        assert "var y = x + 1" in parsed["workload"]

    def test_extracts_imports(self):
        text = "# IMPORT: from math import sqrt\n# ==MODULE==\n"
        parsed = _parse_template(text)
        assert parsed["imports"] == ["from math import sqrt"]

    def test_extracts_keeps(self):
        text = "# ==WORKLOAD==\nvar x = 1\n# KEEP: x int\n# KEEP: y float\n"
        parsed = _parse_template(text)
        assert parsed["keeps"] == [("x", "int"), ("y", "float")]

    def test_keep_default_type(self):
        text = "# ==WORKLOAD==\nvar x = 1\n# KEEP: x\n"
        parsed = _parse_template(text)
        assert parsed["keeps"] == [("x", "int")]

    def test_empty_sections(self):
        text = "# ==MODULE==\n# ==SETUP==\n# ==WORKLOAD==\n"
        parsed = _parse_template(text)
        assert parsed["module"].strip() == ""
        assert parsed["setup"].strip() == ""
        assert parsed["workload"].strip() == ""


# ---------------------------------------------------------------------------
# Token expansion
# ---------------------------------------------------------------------------


class TestTokenExpansion:
    def test_replaces_simple_tokens(self):
        tokens = {"LIST": "List", "APPEND": "append"}
        text = "var a = {{LIST}}[Int]()\na.{{APPEND}}(42)"
        result = _apply_tokens(text, tokens)
        assert result == "var a = List[Int]()\na.append(42)"

    def test_replaces_struct_decorator(self):
        tokens = {"STRUCT_DECORATOR": "@fieldwise_init"}
        result = _apply_tokens("{{STRUCT_DECORATOR}}\nstruct Foo:", tokens)
        assert result == "@fieldwise_init\nstruct Foo:"

    def test_empty_token_value(self):
        tokens = {"STRUCT_DECORATOR": ""}
        result = _apply_tokens("{{STRUCT_DECORATOR}}\nstruct Foo:", tokens)
        assert result == "\nstruct Foo:"


# ---------------------------------------------------------------------------
# Conditional expansion
# ---------------------------------------------------------------------------


class TestConditionalExpansion:
    def test_keeps_modern_removes_legacy(self):
        text = "{{#MODERN}}modern code{{/MODERN}}{{#LEGACY}}legacy code{{/LEGACY}}"
        result = _apply_conditionals(text, "MODERN")
        assert "modern code" in result
        assert "legacy code" not in result

    def test_keeps_legacy_removes_modern(self):
        text = "{{#MODERN}}modern code{{/MODERN}}{{#LEGACY}}legacy code{{/LEGACY}}"
        result = _apply_conditionals(text, "LEGACY")
        assert "legacy code" in result
        assert "modern code" not in result

    def test_multiline_blocks(self):
        text = "before\n{{#MODERN}}\nline1\nline2\n{{/MODERN}}\nafter"
        result = _apply_conditionals(text, "MODERN")
        assert "line1" in result
        assert "line2" in result
        assert "before" in result
        assert "after" in result

    def test_collapses_excessive_blank_lines(self):
        text = "a\n\n\n\n\nb"
        result = _apply_conditionals(text, "MODERN")
        assert "\n\n\n" not in result


# ---------------------------------------------------------------------------
# Full rendering — modern harness
# ---------------------------------------------------------------------------


class TestRenderModern:
    SIMPLE_TEMPLATE = (
        '"""Test benchmark."""\n\n'
        "# ==MODULE==\n\n"
        "# ==SETUP==\n"
        "var n = 10\n\n"
        "# ==WORKLOAD==\n"
        "var total = 0\n"
        "for i in range(n):\n"
        "    total += i\n\n"
        "# KEEP: total int\n"
    )

    def _write_template(self, tmp: Path, text: str) -> Path:
        p = tmp / "test.mojo"
        p.write_text(text)
        return p

    def test_modern_has_benchmark_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.SIMPLE_TEMPLATE)
            result = render_template(path, "0.26.1.0")
            assert "import benchmark" in result
            assert "from benchmark import keep" in result

    def test_modern_has_workload_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.SIMPLE_TEMPLATE)
            result = render_template(path, "0.26.1.0")
            assert "fn workload() capturing:" in result

    def test_modern_has_keep_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.SIMPLE_TEMPLATE)
            result = render_template(path, "0.26.1.0")
            assert "keep(total)" in result

    def test_modern_has_benchmark_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.SIMPLE_TEMPLATE)
            result = render_template(path, "0.26.1.0")
            assert "benchmark.run[workload]" in result

    def test_modern_has_mojomark_ns_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.SIMPLE_TEMPLATE)
            result = render_template(path, "0.26.1.0")
            assert 'print("MOJOMARK_NS"' in result

    def test_modern_main_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.SIMPLE_TEMPLATE)
            result = render_template(path, "0.26.1.0")
            assert "fn main() raises:" in result

    def test_modern_imports_black_box_when_used(self):
        template = '"""Test."""\n\n# ==WORKLOAD==\nvar x = black_box(42)\n\n# KEEP: x int\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), template)
            result = render_template(path, "0.26.1.0")
            assert "black_box" in result
            assert "from benchmark import keep, black_box" in result

    def test_modern_includes_custom_imports(self):
        template = (
            '"""Test."""\n\n'
            "# IMPORT: from math import sqrt\n"
            "# ==WORKLOAD==\nvar x = 1\n# KEEP: x int\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), template)
            result = render_template(path, "0.26.1.0")
            assert "from math import sqrt" in result


# ---------------------------------------------------------------------------
# Full rendering — legacy harness
# ---------------------------------------------------------------------------


class TestRenderLegacy:
    SIMPLE_TEMPLATE = (
        '"""Test benchmark."""\n\n'
        "# ==MODULE==\n\n"
        "# ==SETUP==\n"
        "var n = 10\n\n"
        "# ==WORKLOAD==\n"
        "var total = 0\n"
        "for i in range(n):\n"
        "    total += i\n\n"
        "# KEEP: total int\n"
    )

    def _write_template(self, tmp: Path, text: str) -> Path:
        p = tmp / "test.mojo"
        p.write_text(text)
        return p

    def test_legacy_has_time_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.SIMPLE_TEMPLATE)
            result = render_template(path, "0.7.0")
            assert "from time import now" in result

    def test_legacy_has_no_benchmark_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.SIMPLE_TEMPLATE)
            result = render_template(path, "0.7.0")
            assert "import benchmark" not in result

    def test_legacy_has_timing_vars(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.SIMPLE_TEMPLATE)
            result = render_template(path, "0.7.0")
            assert "_bench_start = now()" in result
            assert "_bench_elapsed = now() - _bench_start" in result

    def test_legacy_has_sentinel_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.SIMPLE_TEMPLATE)
            result = render_template(path, "0.7.0")
            assert "total == -1" in result
            assert 'print("unreachable")' in result

    def test_legacy_has_mojomark_ns_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.SIMPLE_TEMPLATE)
            result = render_template(path, "0.7.0")
            assert 'print("MOJOMARK_NS", _bench_elapsed)' in result

    def test_legacy_main_no_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.SIMPLE_TEMPLATE)
            result = render_template(path, "0.7.0")
            assert "fn main():" in result
            assert "fn main() raises:" not in result

    def test_legacy_float_sentinel(self):
        template = '"""Test."""\n\n# ==WORKLOAD==\nvar x: Float64 = 0.0\n# KEEP: x float\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), template)
            result = render_template(path, "0.7.0")
            assert "x == -1.0" in result

    def test_legacy_str_sentinel(self):
        template = '"""Test."""\n\n# ==WORKLOAD==\nvar s: String = ""\n# KEEP: s str\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), template)
            result = render_template(path, "0.7.0")
            assert "len(s) == 0" in result

    def test_legacy_list_sentinel(self):
        template = (
            '"""Test."""\n\n# ==WORKLOAD==\nvar arr = DynamicVector[Int]()\n# KEEP: arr list\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), template)
            result = render_template(path, "0.7.0")
            assert "arr[0] == -1" in result


# ---------------------------------------------------------------------------
# Token substitution across versions
# ---------------------------------------------------------------------------


class TestTokenSubstitution:
    COLLECTION_TEMPLATE = (
        '"""Test."""\n\n'
        "# ==SETUP==\n"
        "var a = {{LIST}}[Int]()\n"
        "a.{{APPEND}}(42)\n\n"
        "# ==WORKLOAD==\n"
        "var x = a[0]\n\n"
        "# KEEP: x int\n"
    )

    def _write_template(self, tmp: Path, text: str) -> Path:
        p = tmp / "test.mojo"
        p.write_text(text)
        return p

    def test_modern_uses_list_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.COLLECTION_TEMPLATE)
            result = render_template(path, "0.26.1.0")
            assert "List[Int]()" in result
            assert "a.append(42)" in result

    def test_legacy_uses_dynamic_vector(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.COLLECTION_TEMPLATE)
            result = render_template(path, "0.7.0")
            assert "DynamicVector[Int]()" in result
            assert "a.push_back(42)" in result

    def test_transitional_uses_list_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.COLLECTION_TEMPLATE)
            result = render_template(path, "0.25.7.0")
            assert "List[Int]()" in result
            assert "a.append(42)" in result


# ---------------------------------------------------------------------------
# Conditional blocks across versions
# ---------------------------------------------------------------------------


class TestConditionalBlocks:
    COND_TEMPLATE = (
        '"""Test."""\n\n'
        "# ==WORKLOAD==\n"
        "{{#MODERN}}\n"
        "var x = modern_func()\n"
        "{{/MODERN}}\n"
        "{{#LEGACY}}\n"
        "var x = legacy_func()\n"
        "{{/LEGACY}}\n\n"
        "# KEEP: x int\n"
    )

    def _write_template(self, tmp: Path, text: str) -> Path:
        p = tmp / "test.mojo"
        p.write_text(text)
        return p

    def test_modern_keeps_modern_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.COND_TEMPLATE)
            result = render_template(path, "0.26.1.0")
            assert "modern_func()" in result
            assert "legacy_func()" not in result

    def test_legacy_keeps_legacy_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.COND_TEMPLATE)
            result = render_template(path, "0.7.0")
            assert "legacy_func()" in result
            assert "modern_func()" not in result

    def test_transitional_keeps_legacy_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_template(Path(tmp), self.COND_TEMPLATE)
            result = render_template(path, "0.25.7.0")
            assert "legacy_func()" in result
            assert "modern_func()" not in result


# ---------------------------------------------------------------------------
# render_to_file
# ---------------------------------------------------------------------------


class TestRenderToFile:
    def test_writes_file(self):
        template_text = '"""Test."""\n\n# ==WORKLOAD==\nvar x = 1\n# KEEP: x int\n'
        with tempfile.TemporaryDirectory() as tmp:
            tmpl = Path(tmp) / "bench.mojo"
            tmpl.write_text(template_text)

            out_dir = Path(tmp) / "output"
            out_dir.mkdir()

            result = render_to_file(tmpl, out_dir, "0.26.1.0")
            assert result.exists()
            assert result.name == "bench.mojo"
            contents = result.read_text()
            assert "import benchmark" in contents


# ---------------------------------------------------------------------------
# discover_templates
# ---------------------------------------------------------------------------


class TestDiscoverTemplates:
    def test_finds_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "compute").mkdir()
            (base / "compute" / "fib.mojo").write_text("fn main(): pass")

            result = discover_templates(base)
            assert len(result) == 1
            assert result[0][0] == "fib"
            assert result[0][1] == "compute"

    def test_category_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "compute").mkdir()
            (base / "simd").mkdir()
            (base / "compute" / "fib.mojo").write_text("fn main(): pass")
            (base / "simd" / "dot.mojo").write_text("fn main(): pass")

            result = discover_templates(base, category="simd")
            assert len(result) == 1
            assert result[0][0] == "dot"

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert discover_templates(Path(tmp)) == []

    def test_nonexistent_directory(self):
        assert discover_templates(Path("/nonexistent")) == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_strip_blank_edges(self):
        assert _strip_blank_edges("\n\ncode\n\n") == "code"

    def test_strip_blank_edges_preserves_inner(self):
        assert _strip_blank_edges("\na\n\nb\n") == "a\n\nb"
