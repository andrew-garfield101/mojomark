"""Benchmark: Sorting
Category: compute
Measures: Array operations, comparison overhead, memory access patterns.
"""

# ==MODULE==
fn quicksort({{MUT}} arr: {{LIST}}[Int], low: Int, high: Int):
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

# ==SETUP==
var size = 50000

var template = {{LIST}}[Int]()
var seed: Int = 42
for _ in range(size):
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    template.{{APPEND}}(seed)

# ==WORKLOAD==
var arr = {{LIST}}[Int]()
for i in range(size):
    arr.{{APPEND}}(template[i])
quicksort(arr, 0, size - 1)

# KEEP: arr list
