"""Benchmark: Dictionary Operations
Category: collections
Measures: Hash table insert and lookup throughput, hashing overhead, collision handling.

Tests Dict[Int, Int] with sequential inserts and lookups.
Requires Mojo 0.26+ (Int does not implement KeyElement on earlier versions).
"""

# IMPORT: from collections import Dict

# ==MODULE==

# ==SETUP==
var size = 50000

# ==WORKLOAD==
var d = Dict[Int, Int]()

for i in range(size):
    try:
        d[i] = i * 2
    except:
        pass

var checksum: Int = 0
for i in range(size):
    try:
        checksum += d[i]
    except:
        pass

# KEEP: checksum int
