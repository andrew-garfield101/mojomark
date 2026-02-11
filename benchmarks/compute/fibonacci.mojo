"""Benchmark: Recursive Fibonacci
Category: compute
Measures: Function call overhead, recursion optimization, integer arithmetic.

The Python harness compiles this once and runs the binary multiple times,
timing each execution externally. This avoids compiler optimization issues
with in-process loop timing.
"""


fn fibonacci(n: Int) -> Int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


fn main():
    # Run the workload — Python harness handles timing and iterations
    var sink: Int = 0
    for _ in range(10):
        var r = fibonacci(35)
        sink += r

    # Prevent dead code elimination
    if sink == -1:
        print("unreachable")
