"""Benchmark: String Concatenation
Category: strings
Measures: String builder efficiency, memory allocation for growing strings.
"""

# ==MODULE==

# ==SETUP==

# ==WORKLOAD==
var iterations = 50000

var result: String = ""
for i in range(iterations):
    result += "x"

var numeric_str: String = ""
for i in range(iterations):
    numeric_str = String(i)

# KEEP: result str
# KEEP: numeric_str str
