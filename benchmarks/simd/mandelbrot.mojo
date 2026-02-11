"""Benchmark: SIMD Mandelbrot Set
Category: simd
Measures: Explicit SIMD lane operations, divergent control flow across lanes,
floating-point throughput at maximum width, and compiler vectorization quality.

Computes a section of the Mandelbrot set using explicit SIMD types so that
multiple pixels are evaluated in parallel within a single instruction.
"""

from sys.info import simdwidthof

alias WIDTH = 512
alias HEIGHT = 512
alias MAX_ITER = 100

# View window in the complex plane (covers the interesting region)
alias X_MIN: Float64 = -2.0
alias X_MAX: Float64 = 0.6
alias Y_MIN: Float64 = -1.3
alias Y_MAX: Float64 = 1.3

alias SIMD_WIDTH = simdwidthof[DType.float64]()


fn mandelbrot_kernel(cx: SIMD[DType.float64, SIMD_WIDTH],
                     cy: SIMD[DType.float64, SIMD_WIDTH]) -> SIMD[DType.int32, SIMD_WIDTH]:
    """Compute Mandelbrot iteration counts for a SIMD-wide batch of points.

    Each lane independently iterates z = z^2 + c until escape or max iterations.
    Lanes that escape early are masked off while remaining lanes continue.
    """
    var zx = SIMD[DType.float64, SIMD_WIDTH](0)
    var zy = SIMD[DType.float64, SIMD_WIDTH](0)
    var iters = SIMD[DType.int32, SIMD_WIDTH](0)

    for _ in range(MAX_ITER):
        # z^2 = (zx + zy*i)^2 = (zx^2 - zy^2) + (2*zx*zy)*i
        var zx2 = zx * zx
        var zy2 = zy * zy

        # Escape condition: |z|^2 > 4.0 — check per lane
        var magnitude = zx2 + zy2
        var still_inside = magnitude <= 4.0

        # If all lanes have escaped, stop early
        if not still_inside.reduce_or():
            break

        # Update iteration counts only for lanes still inside
        iters = still_inside.select(iters + 1, iters)

        # Compute next z value
        var new_zx = zx2 - zy2 + cx
        zy = 2.0 * zx * zy + cy
        zx = new_zx

    return iters


fn main():
    var dx = (X_MAX - X_MIN) / WIDTH
    var dy = (Y_MAX - Y_MIN) / HEIGHT

    # Accumulate total iteration counts as a checksum
    var total_iters: Int = 0

    for row in range(HEIGHT):
        var cy_scalar = Y_MIN + row * dy

        # Broadcast cy to all SIMD lanes (same row)
        var cy = SIMD[DType.float64, SIMD_WIDTH](cy_scalar)

        # Process columns in SIMD-wide chunks
        var col = 0
        while col + SIMD_WIDTH <= WIDTH:
            # Build cx vector: each lane gets a different column's x coordinate
            var cx: SIMD[DType.float64, SIMD_WIDTH]
            for lane in range(SIMD_WIDTH):
                cx[lane] = X_MIN + (col + lane) * dx

            var iters = mandelbrot_kernel(cx, cy)

            # Accumulate iteration counts
            total_iters += int(iters.reduce_add())

            col += SIMD_WIDTH

        # Handle remaining columns (scalar fallback)
        while col < WIDTH:
            var cx_scalar = X_MIN + col * dx
            var cx_single = SIMD[DType.float64, SIMD_WIDTH](cx_scalar)
            var cy_single = SIMD[DType.float64, SIMD_WIDTH](cy_scalar)
            var iters = mandelbrot_kernel(cx_single, cy_single)
            total_iters += int(iters[0])
            col += 1

    # Prevent dead code elimination
    if total_iters == -1:
        print("unreachable")
