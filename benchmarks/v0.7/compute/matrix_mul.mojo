"""Benchmark: Matrix Multiplication
Category: compute
Measures: Nested loop throughput, floating-point arithmetic, memory access patterns.

Setup (matrix allocation and filling) is excluded from the timing.
Only the triple-loop multiply and checksum accumulation are measured.
"""

from time import now


fn main():
    var n = 128

    # --- Setup (not timed) ---
    var a = DynamicVector[Float64]()
    var b = DynamicVector[Float64]()
    var c = DynamicVector[Float64]()

    var seed: Int = 42
    for _ in range(n * n):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        a.push_back(Float64(seed % 100) / 50.0 - 1.0)
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        b.push_back(Float64(seed % 100) / 50.0 - 1.0)
        c.push_back(0.0)

    # --- Timed section ---
    var _bench_start = now()

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

    var _bench_elapsed = now() - _bench_start

    # Prevent dead code elimination
    if checksum == -1.0:
        print("unreachable")

    # Report timing to harness
    print("MOJOMARK_NS", _bench_elapsed)
