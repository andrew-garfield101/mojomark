"""Benchmark: Explicit SIMD Vectorization
Category: simd
Measures: Direct SIMD register operations, multiply-add throughput,
lane-parallel computation using explicit SIMD types.

Uses explicit SIMD[DType.float32, N] operations rather than relying on
the compiler's auto-vectorization. Tests hardware SIMD unit throughput.
"""

# IMPORT: from sys.info import simdwidthof

# ==MODULE==

{{CONST}} NELTS = simdwidthof[DType.float32]()

# ==SETUP==
var iterations = 500000

# ==WORKLOAD==
var checksum: Float32 = 0.0

for i in range(iterations):
    var scale = Float32(i % 1000) * 0.001 + 0.5
    var offset = Float32((i * 7 + 3) % 1000) * 0.001

    var a = SIMD[DType.float32, NELTS](scale)
    var b = SIMD[DType.float32, NELTS](offset)

    var r = a * b + a
    r = r * r - b
    r = r + a * b

    checksum += r.reduce_add()

# KEEP: checksum float
