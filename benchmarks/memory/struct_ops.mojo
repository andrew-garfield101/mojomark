"""Benchmark: Struct Operations
Category: memory
Measures: Struct creation, field access, and copy overhead.
"""


struct Point3D(CollectionElement):
    var x: Float64
    var y: Float64
    var z: Float64

    fn __init__(inout self, x: Float64, y: Float64, z: Float64):
        self.x = x
        self.y = y
        self.z = z

    fn __copyinit__(inout self, existing: Self):
        self.x = existing.x
        self.y = existing.y
        self.z = existing.z

    fn __moveinit__(inout self, owned existing: Self):
        self.x = existing.x
        self.y = existing.y
        self.z = existing.z


fn distance_squared(a: Point3D, b: Point3D) -> Float64:
    let dx = a.x - b.x
    let dy = a.y - b.y
    let dz = a.z - b.z
    return dx * dx + dy * dy + dz * dz


fn main():
    let size = 100000

    # Create a large array of structs
    var points = DynamicVector[Point3D]()
    var seed: Float64 = 1.0
    for i in range(size):
        seed = (seed * 1.1 + 0.7) % 1000.0
        let p = Point3D(seed, seed * 0.5, seed * 0.3)
        points.push_back(p)

    # Compute pairwise distances (adjacent pairs)
    var total_dist: Float64 = 0.0
    for i in range(size - 1):
        total_dist += distance_squared(points[i], points[i + 1])

    # Prevent dead code elimination
    if total_dist == -1.0:
        print("unreachable")
