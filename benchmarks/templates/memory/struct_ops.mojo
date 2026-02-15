"""Benchmark: Struct Operations
Category: memory
Measures: Struct creation, field access, and copy overhead.
"""

# ==MODULE==
{{STRUCT_DECORATOR}}
struct Point3D({{STRUCT_TRAITS}}):
    var x: Float64
    var y: Float64
    var z: Float64
{{#LEGACY}}
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
{{/LEGACY}}

fn distance_squared(a: Point3D, b: Point3D) -> Float64:
    var dx = a.x - b.x
    var dy = a.y - b.y
    var dz = a.z - b.z
    return dx * dx + dy * dy + dz * dz

# ==SETUP==
var size = 100000

var points = {{LIST}}[Point3D]()
var seed: Float64 = 1.0
for i in range(size):
    seed = (seed * 1.1 + 0.7) % 1000.0
    var p = Point3D(seed, seed * 0.5, seed * 0.3)
    points.{{APPEND}}(p{{MOVE_SUFFIX}})

# ==WORKLOAD==
var total_dist: Float64 = 0.0
for i in range(size - 1):
    total_dist += distance_squared(points[i], points[i + 1])

# KEEP: total_dist float
