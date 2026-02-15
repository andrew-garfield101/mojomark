"""Benchmark: Mandelbrot Set
Category: simd
Measures: Floating-point throughput, branch prediction, loop optimization,
and compiler auto-vectorization quality.

Computes a section of the Mandelbrot set using scalar code. The compiler
is free to auto-vectorize — this tests implicit vectorization quality
across Mojo versions.
"""

# ==MODULE==
{{CONST}} WIDTH = 512
{{CONST}} HEIGHT = 512
{{CONST}} MAX_ITER = 100

{{CONST}} X_MIN: Float64 = -2.0
{{CONST}} X_MAX: Float64 = 0.6
{{CONST}} Y_MIN: Float64 = -1.3
{{CONST}} Y_MAX: Float64 = 1.3


fn mandelbrot_scalar(cx: Float64, cy: Float64) -> Int:
    """Compute Mandelbrot iteration count for a single point."""
    var zx: Float64 = 0.0
    var zy: Float64 = 0.0

    for i in range(MAX_ITER):
        var zx2 = zx * zx
        var zy2 = zy * zy

        if zx2 + zy2 > 4.0:
            return i

        var new_zx = zx2 - zy2 + cx
        zy = 2.0 * zx * zy + cy
        zx = new_zx

    return MAX_ITER

# ==SETUP==

# ==WORKLOAD==
var dx = (X_MAX - X_MIN) / WIDTH
var dy = (Y_MAX - Y_MIN) / HEIGHT
var total_iters: Int = 0

for row in range(HEIGHT):
    var cy = Y_MIN + row * dy

    for col in range(WIDTH):
        var cx = X_MIN + col * dx
        total_iters += mandelbrot_scalar(cx, cy)

# KEEP: total_iters int
