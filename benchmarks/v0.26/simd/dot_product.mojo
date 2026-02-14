"""Benchmark: SIMD Dot Product
Category: simd
Measures: Multiply-accumulate throughput, SIMD vectorization potential, memory bandwidth.

Setup (vector allocation and filling) happens once before benchmarking.
The workload captures the vectors and computes the dot product (read-only).

Uses Mojo's stdlib benchmark module for statistically rigorous timing with
adaptive batching and compiler anti-optimization barriers (keep).
"""

import benchmark
from benchmark import keep


fn main() raises:
    var size = 1000000
    var rounds = 5

    # --- Setup (not timed) ---
    var a = List[Float64]()
    var b = List[Float64]()

    var seed: Float64 = 1.0
    for _ in range(size):
        seed = (seed * 1.1 + 0.3) % 1000.0
        a.append(seed)
        b.append(seed * 0.7 + 1.0)

    # --- Benchmarked workload ---
    fn workload() capturing:
        var checksum: Float64 = 0.0
        for _ in range(rounds):
            var dot: Float64 = 0.0
            for i in range(size):
                dot += a[i] * b[i]
            checksum += dot
        keep(checksum)

    var report = benchmark.run[workload](2, 1_000_000_000, 0.1, 2)
    print("MOJOMARK_NS", Int(report.mean("ns")))
