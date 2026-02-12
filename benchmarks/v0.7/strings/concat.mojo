"""Benchmark: String Concatenation
Category: strings
Measures: String builder efficiency, memory allocation for growing strings.

The entire workload (building strings through concatenation) is the thing
we are measuring, so the full body is timed.
"""

from time import now


fn main():
    var iterations = 50000

    # --- Timed section ---
    var _bench_start = now()

    # Build a long string through repeated concatenation
    var result: String = ""
    for i in range(iterations):
        result += "x"

    # Also test string conversion from integers
    var numeric_str: String = ""
    for i in range(iterations):
        numeric_str = String(i)

    var _bench_elapsed = now() - _bench_start

    # Prevent dead code elimination
    if len(result) == 0 or len(numeric_str) == 0:
        print("unreachable")

    # Report timing to harness
    print("MOJOMARK_NS", _bench_elapsed)
