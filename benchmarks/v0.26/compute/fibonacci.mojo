"""Benchmark: Recursive Fibonacci
Category: compute
Measures: Function call overhead, recursion optimization, integer arithmetic.

Uses Mojo's stdlib benchmark module for statistically rigorous timing with
adaptive batching and compiler anti-optimization barriers (keep).
"""

import benchmark
from benchmark import keep, black_box


fn fibonacci(n: Int) -> Int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


fn main() raises:
    fn workload() capturing:
        var sink: Int = 0
        for _ in range(10):
            sink += fibonacci(black_box(35))
        keep(sink)

    var report = benchmark.run[workload](2, 1_000_000_000, 0.1, 2)
    print("MOJOMARK_NS", Int(report.mean("ns")))
