"""Benchmark: String Concatenation
Category: strings
Measures: String builder efficiency, memory allocation for growing strings.

The entire workload (building strings through concatenation) is what we are
measuring, so there is no separate setup phase.

Uses Mojo's stdlib benchmark module for statistically rigorous timing with
adaptive batching and compiler anti-optimization barriers (keep).
"""

import benchmark
from benchmark import keep


fn main() raises:
    fn workload() capturing:
        var iterations = 50000

        # Build a long string through repeated concatenation
        var result: String = ""
        for i in range(iterations):
            result += "x"

        # Also test string conversion from integers
        var numeric_str: String = ""
        for i in range(iterations):
            numeric_str = String(i)

        keep(result)
        keep(numeric_str)

    var report = benchmark.run[workload](2, 1_000_000_000, 0.1, 2)
    print("MOJOMARK_NS", Int(report.mean("ns")))
