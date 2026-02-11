"""Benchmark: String Concatenation
Category: strings
Measures: String builder efficiency, memory allocation for growing strings.
"""


fn main():
    var iterations = 50000

    # Build a long string through repeated concatenation
    var result: String = ""
    for i in range(iterations):
        result += "x"

    # Also test string conversion from integers
    var numeric_str: String = ""
    for i in range(iterations):
        numeric_str = String(i)

    # Prevent dead code elimination
    if len(result) == 0 or len(numeric_str) == 0:
        print("unreachable")
