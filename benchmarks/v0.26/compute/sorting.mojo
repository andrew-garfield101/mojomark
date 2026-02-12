"""Benchmark: Sorting
Category: compute
Measures: Array operations, comparison overhead, memory access patterns.

Setup (array construction) is excluded from the timing.
Only the quicksort itself is measured.
"""

from time import perf_counter_ns


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


fn main():
    var size = 50000

    # --- Setup (not timed) ---
    var arr = List[Int]()
    var seed: Int = 42
    for _ in range(size):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        arr.append(seed)

    # --- Timed section ---
    var _bench_start = perf_counter_ns()

    quicksort(arr, 0, size - 1)

    var _bench_elapsed = perf_counter_ns() - _bench_start

    # Prevent dead code elimination
    if arr[0] == -1:
        print("unreachable")

    # Report timing to harness
    print("MOJOMARK_NS", _bench_elapsed)
