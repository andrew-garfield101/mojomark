"""Benchmark: SIMD Vector Math
Category: simd
Measures: SIMD throughput, vectorized arithmetic, memory bandwidth.
"""
from math import sqrt


fn main():
    var size = 1000000

    # Element-wise vector operations on large arrays
    var a = List[Float64]()
    var b = List[Float64]()
    var c = List[Float64]()

    # Initialize with pseudo-random values
    var seed: Float64 = 1.0
    for i in range(size):
        seed = (seed * 1.1 + 0.3) % 1000.0
        a.append(seed)
        b.append(seed * 0.7 + 1.0)
        c.append(0.0)

    # Vector add + multiply + sqrt pipeline
    var checksum: Float64 = 0.0
    for i in range(size):
        var val = (a[i] + b[i]) * 0.5
        c[i] = sqrt(val)
        checksum += c[i]

    # Prevent dead code elimination
    if checksum == -1.0:
        print("unreachable")
