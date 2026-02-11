"""Benchmark: SIMD Vector Math
Category: simd
Measures: SIMD throughput, vectorized arithmetic, memory bandwidth.
"""
from math import sqrt


fn main():
    let size = 1000000

    # Element-wise vector operations on large arrays
    var a = DynamicVector[Float64]()
    var b = DynamicVector[Float64]()
    var c = DynamicVector[Float64]()

    # Initialize with pseudo-random values
    var seed: Float64 = 1.0
    for i in range(size):
        seed = (seed * 1.1 + 0.3) % 1000.0
        a.push_back(seed)
        b.push_back(seed * 0.7 + 1.0)
        c.push_back(0.0)

    # Vector add + multiply + sqrt pipeline
    var checksum: Float64 = 0.0
    for i in range(size):
        let val = (a[i] + b[i]) * 0.5
        c[i] = sqrt(val)
        checksum += c[i]

    # Prevent dead code elimination
    if checksum == -1.0:
        print("unreachable")
