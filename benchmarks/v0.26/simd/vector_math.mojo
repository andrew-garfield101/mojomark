"""Benchmark: SIMD Vector Math
Category: simd
Measures: SIMD throughput, vectorized arithmetic, memory bandwidth.

Setup (vector allocation) happens once before benchmarking.
The workload captures the input vectors and creates a fresh output vector
each iteration for the add/multiply/sqrt pipeline.

Uses Mojo's stdlib benchmark module for statistically rigorous timing with
adaptive batching and compiler anti-optimization barriers (keep).
"""

import benchmark
from benchmark import keep
from math import sqrt


fn main() raises:
    var size = 1000000

    # --- Setup (not timed) ---
    var a = List[Float64]()
    var b = List[Float64]()

    var seed: Float64 = 1.0
    for i in range(size):
        seed = (seed * 1.1 + 0.3) % 1000.0
        a.append(seed)
        b.append(seed * 0.7 + 1.0)

    # --- Benchmarked workload ---
    fn workload() capturing:
        var checksum: Float64 = 0.0
        for i in range(size):
            var val = (a[i] + b[i]) * 0.5
            checksum += sqrt(val)
        keep(checksum)

    var report = benchmark.run[workload](2, 1_000_000_000, 0.1, 2)
    print("MOJOMARK_NS", Int(report.mean("ns")))
