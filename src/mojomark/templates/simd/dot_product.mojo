"""Benchmark: SIMD Dot Product
Category: simd
Measures: Multiply-accumulate throughput, SIMD vectorization potential, memory bandwidth.
"""

# ==MODULE==

# ==SETUP==
var size = 1000000
var rounds = 5

var a = {{LIST}}[Float64]()
var b = {{LIST}}[Float64]()

var seed: Float64 = 1.0
for _ in range(size):
    seed = (seed * 1.1 + 0.3) % 1000.0
    a.{{APPEND}}(seed)
    b.{{APPEND}}(seed * 0.7 + 1.0)

# ==WORKLOAD==
var checksum: Float64 = 0.0
for _ in range(rounds):
    var dot: Float64 = 0.0
    for i in range(size):
        dot += a[i] * b[i]
    checksum += dot

# KEEP: checksum float
