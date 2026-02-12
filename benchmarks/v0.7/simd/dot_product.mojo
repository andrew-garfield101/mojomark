"""Benchmark: SIMD Dot Product
Category: simd
Measures: Multiply-accumulate throughput, SIMD vectorization potential, memory bandwidth.

Setup (vector allocation and filling) is excluded from the timing.
Only the dot-product computation rounds are measured.
"""

from time import now


fn main():
    var size = 1000000
    var rounds = 5

    # --- Setup (not timed) ---
    var a = DynamicVector[Float64]()
    var b = DynamicVector[Float64]()

    var seed: Float64 = 1.0
    for _ in range(size):
        seed = (seed * 1.1 + 0.3) % 1000.0
        a.push_back(seed)
        b.push_back(seed * 0.7 + 1.0)

    # --- Timed section ---
    var _bench_start = now()

    var checksum: Float64 = 0.0
    for _ in range(rounds):
        var dot: Float64 = 0.0
        for i in range(size):
            dot += a[i] * b[i]
        checksum += dot

    var _bench_elapsed = now() - _bench_start

    # Prevent dead code elimination
    if checksum == -1.0:
        print("unreachable")

    # Report timing to harness
    print("MOJOMARK_NS", _bench_elapsed)
