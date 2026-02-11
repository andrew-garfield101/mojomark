"""Benchmark: Heap Allocation
Category: memory
Measures: Dynamic memory allocation throughput, DynamicVector grow/shrink patterns.
"""


fn main():
    var num_vectors = 100
    var elements_per_vector = 10000

    var checksum: Int = 0

    # Repeatedly create, grow, and discard dynamic vectors
    for v in range(num_vectors):
        var vec = List[Int]()

        # Grow phase — trigger multiple internal reallocations
        for i in range(elements_per_vector):
            vec.append(i * v + 1)

        # Read phase — access to prevent elimination
        for i in range(elements_per_vector):
            checksum += vec[i]

        # Vec goes out of scope here — freed each iteration

    # Prevent dead code elimination
    if checksum == -1:
        print("unreachable")
