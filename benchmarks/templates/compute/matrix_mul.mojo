"""Benchmark: Matrix Multiplication
Category: compute
Measures: Nested loop throughput, floating-point arithmetic, memory access patterns.
"""

# ==MODULE==

# ==SETUP==
var n = 128

var a = {{LIST}}[Float64]()
var b = {{LIST}}[Float64]()

var seed: Int = 42
for _ in range(n * n):
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    a.{{APPEND}}(Float64(seed % 100) / 50.0 - 1.0)
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    b.{{APPEND}}(Float64(seed % 100) / 50.0 - 1.0)

# ==WORKLOAD==
var c = {{LIST}}[Float64]()
for _ in range(n * n):
    c.{{APPEND}}(0.0)

for i in range(n):
    for k in range(n):
        var a_ik = a[i * n + k]
        for j in range(n):
            c[i * n + j] += a_ik * b[k * n + j]

var checksum: Float64 = 0.0
for i in range(n * n):
    checksum += c[i]

# KEEP: checksum float
