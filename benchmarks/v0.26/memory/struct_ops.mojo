"""Benchmark: Struct Operations
Category: memory
Measures: Struct creation, field access, and copy overhead.

Setup (building the points array) is excluded from the timing.
Only the pairwise distance computation is measured.

Uses @fieldwise_init + explicit Copyable/Movable conformance (modern Mojo).
"""

from time import perf_counter_ns


@fieldwise_init
struct Point3D(Copyable, Movable):
    var x: Float64
    var y: Float64
    var z: Float64


fn distance_squared(a: Point3D, b: Point3D) -> Float64:
    var dx = a.x - b.x
    var dy = a.y - b.y
    var dz = a.z - b.z
    return dx * dx + dy * dy + dz * dz


fn main():
    var size = 100000

    # --- Setup (not timed) ---
    var points = List[Point3D]()
    var seed: Float64 = 1.0
    for i in range(size):
        seed = (seed * 1.1 + 0.7) % 1000.0
        var p = Point3D(seed, seed * 0.5, seed * 0.3)
        points.append(p^)

    # --- Timed section ---
    var _bench_start = perf_counter_ns()

    # Compute pairwise distances (adjacent pairs)
    var total_dist: Float64 = 0.0
    for i in range(size - 1):
        total_dist += distance_squared(points[i], points[i + 1])

    var _bench_elapsed = perf_counter_ns() - _bench_start

    # Prevent dead code elimination
    if total_dist == -1.0:
        print("unreachable")

    # Report timing to harness
    print("MOJOMARK_NS", _bench_elapsed)
