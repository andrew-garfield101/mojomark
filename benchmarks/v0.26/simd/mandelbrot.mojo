"""Benchmark: Mandelbrot Set
Category: simd
Measures: Floating-point throughput, branch prediction, loop optimization,
and compiler auto-vectorization quality.

Computes a section of the Mandelbrot set using scalar code that the compiler
is free to auto-vectorize.  This tests what the compiler gives you implicitly
rather than forcing explicit SIMD intrinsics (which have unstable APIs across
Mojo versions).

Uses Mojo's stdlib benchmark module for statistically rigorous timing with
adaptive batching and compiler anti-optimization barriers (keep).
"""

import benchmark
from benchmark import keep

comptime WIDTH = 512
comptime HEIGHT = 512
comptime MAX_ITER = 100

# View window in the complex plane (covers the interesting region)
comptime X_MIN: Float64 = -2.0
comptime X_MAX: Float64 = 0.6
comptime Y_MIN: Float64 = -1.3
comptime Y_MAX: Float64 = 1.3


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


fn main() raises:
    fn workload() capturing:
        var dx = (X_MAX - X_MIN) / WIDTH
        var dy = (Y_MAX - Y_MIN) / HEIGHT
        var total_iters: Int = 0

        for row in range(HEIGHT):
            var cy = Y_MIN + row * dy

            for col in range(WIDTH):
                var cx = X_MIN + col * dx
                total_iters += mandelbrot_scalar(cx, cy)

        keep(total_iters)

    var report = benchmark.run[workload](2, 1_000_000_000, 0.1, 2)
    print("MOJOMARK_NS", Int(report.mean("ns")))
