"""Benchmark: SIMD Vector Math
Category: simd
Measures: SIMD throughput, vectorized arithmetic, memory bandwidth.
"""

# IMPORT: from math import sqrt

# ==MODULE==

# ==SETUP==
var size = 1000000

var a = {{LIST}}[Float64]()
var b = {{LIST}}[Float64]()

var seed: Float64 = 1.0
for i in range(size):
    seed = (seed * 1.1 + 0.3) % 1000.0
    a.{{APPEND}}(seed)
    b.{{APPEND}}(seed * 0.7 + 1.0)

# ==WORKLOAD==
var checksum: Float64 = 0.0
for i in range(size):
    var val = (a[i] + b[i]) * 0.5
    checksum += sqrt(val)

# KEEP: checksum float
