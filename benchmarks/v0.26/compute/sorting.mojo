"""Benchmark: Sorting
Category: compute
Measures: Array operations, comparison overhead, memory access patterns.

A template array is built once during setup. The workload copies the template
into a fresh array each iteration so quicksort always operates on unsorted data.

Uses Mojo's stdlib benchmark module for statistically rigorous timing with
adaptive batching and compiler anti-optimization barriers (keep).
"""

import benchmark
from benchmark import keep


fn quicksort(mut arr: List[Int], low: Int, high: Int):
    if low >= high:
        return
    var pivot = arr[high]
    var i = low - 1
    for j in range(low, high):
        if arr[j] <= pivot:
            i += 1
            var tmp = arr[i]
            arr[i] = arr[j]
            arr[j] = tmp
    var tmp = arr[i + 1]
    arr[i + 1] = arr[high]
    arr[high] = tmp
    var pi = i + 1
    quicksort(arr, low, pi - 1)
    quicksort(arr, pi + 1, high)


fn main() raises:
    var size = 50000

    # --- Setup: build template array (not timed) ---
    var template = List[Int]()
    var seed: Int = 42
    for _ in range(size):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        template.append(seed)

    # --- Benchmarked workload ---
    fn workload() capturing:
        # Copy template so each iteration sorts fresh unsorted data
        var arr = List[Int]()
        for i in range(size):
            arr.append(template[i])
        quicksort(arr, 0, size - 1)
        keep(arr)

    var report = benchmark.run[workload](2, 1_000_000_000, 0.1, 2)
    print("MOJOMARK_NS", Int(report.mean("ns")))
