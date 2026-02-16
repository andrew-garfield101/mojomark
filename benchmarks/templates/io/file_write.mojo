"""Benchmark: File Write
Category: io
Measures: Sequential file write throughput, syscall overhead, I/O buffering.

Writes ~100KB of data to a temporary file per iteration.
Modern Mojo only (uses open() built-in).
"""

# ==MODULE==

# ==SETUP==
var path = String("/tmp/mojomark_bench_write.txt")
var num_chunks = 100

var data = String("")
for _ in range(1024):
    data += "A"
data += "\n"

# ==WORKLOAD==
var chunks_written: Int = 0
try:
    var f = open(path, "w")
    for _ in range(num_chunks):
        f.write(data)
        chunks_written += 1
    f.close()
except:
    pass

# KEEP: chunks_written int
