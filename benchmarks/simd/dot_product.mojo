"""Benchmark: SIMD Dot Product
Category: simd
Measures: Multiply-accumulate throughput, SIMD vectorization potential, memory bandwidth.
"""


fn main():
    var size = 1000000
    var rounds = 5

    # Allocate two large vectors
    var a = List[Float64]()
    var b = List[Float64]()

    # Fill with LCG-seeded pseudo-random values
    var seed: Float64 = 1.0
    for _ in range(size):
        seed = (seed * 1.1 + 0.3) % 1000.0
        a.append(seed)
        b.append(seed * 0.7 + 1.0)

    # Run multiple rounds of dot product to increase measurement window
    var checksum: Float64 = 0.0
    for _ in range(rounds):
        var dot: Float64 = 0.0
        for i in range(size):
            dot += a[i] * b[i]
        checksum += dot

    # Prevent dead code elimination
    if checksum == -1.0:
        print("unreachable")
