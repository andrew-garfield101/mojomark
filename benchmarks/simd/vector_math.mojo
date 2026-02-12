"""Benchmark: SIMD Vector Math
Category: simd
Measures: SIMD throughput, vectorized arithmetic, memory bandwidth.

Setup (vector allocation) is excluded from the timing.
Only the add/multiply/sqrt pipeline is measured.
"""

from math import sqrt
from time import now


fn main():
    var size = 1000000

    # --- Setup (not timed) ---
    var a = DynamicVector[Float64]()
    var b = DynamicVector[Float64]()
    var c = DynamicVector[Float64]()

    var seed: Float64 = 1.0
    for i in range(size):
        seed = (seed * 1.1 + 0.3) % 1000.0
        a.push_back(seed)
        b.push_back(seed * 0.7 + 1.0)
        c.push_back(0.0)

    # --- Timed section ---
    var _bench_start = now()

    var checksum: Float64 = 0.0
    for i in range(size):
        var val = (a[i] + b[i]) * 0.5
        c[i] = sqrt(val)
        checksum += c[i]

    var _bench_elapsed = now() - _bench_start

    # Prevent dead code elimination
    if checksum == -1.0:
        print("unreachable")

    # Report timing to harness
    print("MOJOMARK_NS", _bench_elapsed)
