"""Benchmark: Recursive Fibonacci
Category: compute
Measures: Function call overhead, recursion optimization, integer arithmetic.
"""

# ==MODULE==
fn fibonacci(n: Int) -> Int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

# ==SETUP==

# ==WORKLOAD==
var sink: Int = 0
var fib_n: Int = 25
for _ in range(10):
    sink += fibonacci(fib_n)
    # Data-dependent input: the next call's argument depends on the
    # accumulated result of all previous calls.  No compiler can
    # constant-fold this because resolving fibonacci outputs through
    # modular arithmetic is not statically computable.
    fib_n = 25 + (sink % 11)

# KEEP: sink int
