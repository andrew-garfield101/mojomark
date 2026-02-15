"""Benchmark: Heap Allocation
Category: memory
Measures: Dynamic memory allocation throughput, grow/shrink patterns.
"""

# ==MODULE==

# ==SETUP==

# ==WORKLOAD==
var num_vectors = 100
var elements_per_vector = 10000
var checksum: Int = 0

for v in range(num_vectors):
    var vec = {{LIST}}[Int]()

    for i in range(elements_per_vector):
        vec.{{APPEND}}(i * v + 1)

    for i in range(elements_per_vector):
        checksum += vec[i]

# KEEP: checksum int
