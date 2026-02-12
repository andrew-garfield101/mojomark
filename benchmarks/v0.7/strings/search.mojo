"""Benchmark: Substring Search
Category: strings
Measures: String traversal, character comparison, search algorithm throughput.

Setup (building the haystack string and defining needles) is excluded from the
timing.  Only the sliding-window search loops are measured.
"""

from time import now


fn main():
    var haystack_len = 100000

    # --- Setup (not timed) ---
    # Build a haystack string from LCG-seeded character generation
    var haystack: String = ""
    var seed: Int = 42
    for _ in range(haystack_len):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        # Map to printable ASCII range (32-126)
        let char_code = (seed % 95) + 32
        haystack += chr(char_code)

    # Define needles of varying lengths to search for
    var needle_short: String = "abc"
    var needle_medium: String = "hello!?x"
    var needle_long: String = "the quick brown fox!"

    var h_len = len(haystack)

    # --- Timed section ---
    var _bench_start = now()

    var total_matches: Int = 0

    # Short needle search
    var ns = len(needle_short)
    for i in range(h_len - ns + 1):
        var found = True
        for j in range(ns):
            if haystack[i + j] != needle_short[j]:
                found = False
                break
        if found:
            total_matches += 1

    # Medium needle search
    var nm = len(needle_medium)
    for i in range(h_len - nm + 1):
        var found = True
        for j in range(nm):
            if haystack[i + j] != needle_medium[j]:
                found = False
                break
        if found:
            total_matches += 1

    # Long needle search
    var nl = len(needle_long)
    for i in range(h_len - nl + 1):
        var found = True
        for j in range(nl):
            if haystack[i + j] != needle_long[j]:
                found = False
                break
        if found:
            total_matches += 1

    var _bench_elapsed = now() - _bench_start

    # Prevent dead code elimination
    if total_matches == -1:
        print("unreachable")

    # Report timing to harness
    print("MOJOMARK_NS", _bench_elapsed)
