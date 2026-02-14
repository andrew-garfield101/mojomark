"""Benchmark: Matrix Multiplication
Category: compute
Measures: Nested loop throughput, floating-point arithmetic, memory access patterns.

Setup (matrix allocation and filling) happens once before benchmarking.
The workload captures the input matrices and creates a fresh result matrix
each iteration so benchmark.run can call it repeatedly.

Uses Mojo's stdlib benchmark module for statistically rigorous timing with
adaptive batching and compiler anti-optimization barriers (keep).
"""

import benchmark
from benchmark import keep


fn main() raises:
    var n = 128

    # --- Setup (not timed) ---
    var a = List[Float64]()
    var b = List[Float64]()

    var seed: Int = 42
    for _ in range(n * n):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        a.append(Float64(seed % 100) / 50.0 - 1.0)
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        b.append(Float64(seed % 100) / 50.0 - 1.0)

    # --- Benchmarked workload ---
    fn workload() capturing:
        # Fresh result matrix each iteration
        var c = List[Float64]()
        for _ in range(n * n):
            c.append(0.0)

        # Naive triple-loop matrix multiply: C = A * B
        for i in range(n):
            for k in range(n):
                var a_ik = a[i * n + k]
                for j in range(n):
                    c[i * n + j] += a_ik * b[k * n + j]

        # Accumulate checksum from result matrix
        var checksum: Float64 = 0.0
        for i in range(n * n):
            checksum += c[i]
        keep(checksum)

    var report = benchmark.run[workload](2, 1_000_000_000, 0.1, 2)
    print("MOJOMARK_NS", Int(report.mean("ns")))
