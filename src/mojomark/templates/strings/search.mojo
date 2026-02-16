"""Benchmark: Substring Search
Category: strings
Measures: String/byte traversal, comparison, search algorithm throughput.
"""

# ==MODULE==

# ==SETUP==
var haystack_len = 100000

var haystack: String = ""
var seed: Int = 42
for _ in range(haystack_len):
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    var char_code = (seed % 95) + 32
    haystack += chr(char_code)

var needle_short: String = "abc"
var needle_medium: String = "hello!?x"
var needle_long: String = "the quick brown fox!"

{{#MODERN}}
var h_bytes = haystack.as_bytes()
var ns_bytes = needle_short.as_bytes()
var nm_bytes = needle_medium.as_bytes()
var nl_bytes = needle_long.as_bytes()
var h_len = len(h_bytes)
{{/MODERN}}
{{#LEGACY}}
var h_len = len(haystack)
{{/LEGACY}}

# ==WORKLOAD==
var total_matches: Int = 0

# Short needle search
{{#MODERN}}
var ns = len(ns_bytes)
{{/MODERN}}
{{#LEGACY}}
var ns = len(needle_short)
{{/LEGACY}}
for i in range(h_len - ns + 1):
    var found = True
    for j in range(ns):
{{#MODERN}}
        if h_bytes[i + j] != ns_bytes[j]:
{{/MODERN}}
{{#LEGACY}}
        if haystack[i + j] != needle_short[j]:
{{/LEGACY}}
            found = False
            break
    if found:
        total_matches += 1

# Medium needle search
{{#MODERN}}
var nm = len(nm_bytes)
{{/MODERN}}
{{#LEGACY}}
var nm = len(needle_medium)
{{/LEGACY}}
for i in range(h_len - nm + 1):
    var found = True
    for j in range(nm):
{{#MODERN}}
        if h_bytes[i + j] != nm_bytes[j]:
{{/MODERN}}
{{#LEGACY}}
        if haystack[i + j] != needle_medium[j]:
{{/LEGACY}}
            found = False
            break
    if found:
        total_matches += 1

# Long needle search
{{#MODERN}}
var nl = len(nl_bytes)
{{/MODERN}}
{{#LEGACY}}
var nl = len(needle_long)
{{/LEGACY}}
for i in range(h_len - nl + 1):
    var found = True
    for j in range(nl):
{{#MODERN}}
        if h_bytes[i + j] != nl_bytes[j]:
{{/MODERN}}
{{#LEGACY}}
        if haystack[i + j] != needle_long[j]:
{{/LEGACY}}
            found = False
            break
    if found:
        total_matches += 1

# KEEP: total_matches int
