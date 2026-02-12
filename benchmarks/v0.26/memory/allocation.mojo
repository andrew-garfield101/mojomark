"""Benchmark: Heap Allocation
Category: memory
Measures: Dynamic memory allocation throughput, List grow/shrink patterns.

The entire allocation/grow/read cycle is the workload here — there is no
separate setup phase, so the full loop is timed.
"""

from time import perf_counter_ns


fn main():
    var num_vectors = 100
    var elements_per_vector = 10000

    # --- Timed section ---
    var _bench_start = perf_counter_ns()

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

    var _bench_elapsed = perf_counter_ns() - _bench_start

    # Prevent dead code elimination
    if checksum == -1:
        print("unreachable")

    # Report timing to harness
    print("MOJOMARK_NS", _bench_elapsed)
