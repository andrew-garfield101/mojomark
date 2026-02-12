"""Benchmark: Substring Search
Category: strings
Measures: String/byte traversal, comparison, search algorithm throughput.

Setup (building the haystack string and defining needles) is excluded from the
timing.  Only the sliding-window search loops are measured.

Uses byte-level comparison via as_bytes() — the modern Mojo String API treats
strings as UTF-8 and no longer supports direct integer indexing.
"""

from time import perf_counter_ns


fn main():
    var haystack_len = 100000

    # --- Setup (not timed) ---
    var haystack: String = ""
    var seed: Int = 42
    for _ in range(haystack_len):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        var char_code = (seed % 95) + 32
        haystack += chr(char_code)

    var needle_short: String = "abc"
    var needle_medium: String = "hello!?x"
    var needle_long: String = "the quick brown fox!"

    # Work at byte level for fast comparison (all ASCII)
    var h_bytes = haystack.as_bytes()
    var ns_bytes = needle_short.as_bytes()
    var nm_bytes = needle_medium.as_bytes()
    var nl_bytes = needle_long.as_bytes()

    var h_len = len(h_bytes)

    # --- Timed section ---
    var _bench_start = perf_counter_ns()

    var total_matches: Int = 0

    # Short needle search
    var ns = len(ns_bytes)
    for i in range(h_len - ns + 1):
        var found = True
        for j in range(ns):
            if h_bytes[i + j] != ns_bytes[j]:
                found = False
                break
        if found:
            total_matches += 1

    # Medium needle search
    var nm = len(nm_bytes)
    for i in range(h_len - nm + 1):
        var found = True
        for j in range(nm):
            if h_bytes[i + j] != nm_bytes[j]:
                found = False
                break
        if found:
            total_matches += 1

    # Long needle search
    var nl = len(nl_bytes)
    for i in range(h_len - nl + 1):
        var found = True
        for j in range(nl):
            if h_bytes[i + j] != nl_bytes[j]:
                found = False
                break
        if found:
            total_matches += 1

    var _bench_elapsed = perf_counter_ns() - _bench_start

    # Prevent dead code elimination
    if total_matches == -1:
        print("unreachable")

    # Report timing to harness
    print("MOJOMARK_NS", _bench_elapsed)
