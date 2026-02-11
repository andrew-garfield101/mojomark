"""Benchmark: Matrix Multiplication
Category: compute
Measures: Nested loop throughput, floating-point arithmetic, memory access patterns.
"""


fn main():
    var n = 128

    # Allocate flattened NxN matrices (row-major)
    var a = List[Float64]()
    var b = List[Float64]()
    var c = List[Float64]()

    # Fill A and B with LCG-seeded pseudo-random values
    var seed: Int = 42
    for _ in range(n * n):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        a.append(Float64(seed % 100) / 50.0 - 1.0)
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        b.append(Float64(seed % 100) / 50.0 - 1.0)
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

    # Prevent dead code elimination
    if checksum == -1.0:
        print("unreachable")
