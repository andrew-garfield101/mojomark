"""Benchmark: Recursive Fibonacci
Category: compute
Measures: Function call overhead, recursion optimization, integer arithmetic.

Timing is measured inside Mojo via ``time.now()`` so that only the hot loop
is captured — process-spawn and linker overhead are excluded.
"""

from time import now


fn fibonacci(n: Int) -> Int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


fn main():
    # Timed section — only the computational work
    var _bench_start = now()

    var sink: Int = 0
    for _ in range(10):
        var r = fibonacci(35)
        sink += r

    var _bench_elapsed = now() - _bench_start

    # Prevent dead code elimination
    if sink == -1:
        print("unreachable")

    # Report timing to harness
    print("MOJOMARK_NS", _bench_elapsed)
