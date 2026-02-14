"""Benchmark: Heap Allocation
Category: memory
Measures: Dynamic memory allocation throughput, List grow/shrink patterns.

The entire allocation/grow/read cycle is the workload — there is no separate
setup phase.

Uses Mojo's stdlib benchmark module for statistically rigorous timing with
adaptive batching and compiler anti-optimization barriers (keep).
"""

import benchmark
from benchmark import keep


fn main() raises:
    fn workload() capturing:
        var num_vectors = 100
        var elements_per_vector = 10000
        var checksum: Int = 0

        # Repeatedly create, grow, and discard dynamic lists
        for v in range(num_vectors):
            var vec = List[Int]()

            # Grow phase — trigger multiple internal reallocations
            for i in range(elements_per_vector):
                vec.append(i * v + 1)

            # Read phase — access to prevent elimination
            for i in range(elements_per_vector):
                checksum += vec[i]

            # Vec goes out of scope here — freed each iteration

        keep(checksum)

    var report = benchmark.run[workload](2, 1_000_000_000, 0.1, 2)
    print("MOJOMARK_NS", Int(report.mean("ns")))
