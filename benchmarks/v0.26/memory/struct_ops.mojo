"""Benchmark: Struct Operations
Category: memory
Measures: Struct creation, field access, and copy overhead.

Setup (building the points array) happens once before benchmarking.
The workload captures the points list and computes pairwise distances
(read-only access).

Uses Mojo's stdlib benchmark module for statistically rigorous timing with
adaptive batching and compiler anti-optimization barriers (keep).
Uses @fieldwise_init + explicit Copyable/Movable conformance (modern Mojo).
"""

import benchmark
from benchmark import keep


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


fn main() raises:
    var size = 100000

    # --- Setup (not timed) ---
    var points = List[Point3D]()
    var seed: Float64 = 1.0
    for i in range(size):
        seed = (seed * 1.1 + 0.7) % 1000.0
        var p = Point3D(seed, seed * 0.5, seed * 0.3)
        points.append(p^)

    # --- Benchmarked workload ---
    fn workload() capturing:
        # Compute pairwise distances (adjacent pairs) — read-only
        var total_dist: Float64 = 0.0
        for i in range(size - 1):
            total_dist += distance_squared(points[i], points[i + 1])
        keep(total_dist)

    var report = benchmark.run[workload](2, 1_000_000_000, 0.1, 2)
    print("MOJOMARK_NS", Int(report.mean("ns")))
