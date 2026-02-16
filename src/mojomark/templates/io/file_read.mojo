"""Benchmark: File Read
Category: io
Measures: Sequential file read throughput, syscall overhead, buffer management.

Reads a ~100KB file in a single call per iteration.
Modern Mojo only (uses open() built-in).
"""

# ==MODULE==

# ==SETUP==
var path = String("/tmp/mojomark_bench_read.txt")

var write_data = String("")
for _ in range(1024):
    write_data += "A"
write_data += "\n"

try:
    var setup_f = open(path, "w")
    for _ in range(100):
        setup_f.write(write_data)
    setup_f.close()
except:
    pass

# ==WORKLOAD==
var bytes_read: Int = 0
try:
    var f = open(path, "r")
    var content = f.read()
    bytes_read = len(content)
    f.close()
except:
    pass

# KEEP: bytes_read int
