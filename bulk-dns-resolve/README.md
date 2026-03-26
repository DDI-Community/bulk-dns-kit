# dnsweep 🔍

A fast, multi-threaded CLI tool for bulk DNS resolution — resolve hundreds of hostnames across multiple domains in seconds using a DNS server of your choice.

---

## Overview

`dnsweep` takes a list of **hostnames** and a list of **domains**, combines them into fully qualified domain names (FQDNs), and resolves each one against a specified DNS server in parallel. Results are printed to the terminal (with colour-coded output) and optionally exported to CSV or JSON.

Useful for:
- Network audits and asset discovery
- Verifying DNS records across multiple domains and record types
- Checking hostname presence in split-horizon DNS environments
- Bulk validation of DNS migrations

---

## Requirements

- Python 3.10+
- [`dnspython`](https://www.dnspython.org/)
- [`tqdm`](https://github.com/tqdm/tqdm) *(optional — enables progress bar)*

Install dependencies:

```bash
pip install dnspython
pip install dnspython tqdm   # with optional progress bar
```

---

## Usage

```bash
python script-v0.2.py -d devices.txt -D domains.txt -s 192.168.1.1
```

### Arguments

| Argument | Short | Required | Default | Description |
|---|---|---|---|---|
| `--devices` | `-d` | ✅ | — | File with hostnames, one per line |
| `--domains` | `-D` | ✅ | — | File with domains, one per line |
| `--server` | `-s` | ❌ | *(prompted)* | DNS server IP to query |
| `--record-type` | `-r` | ❌ | `A` | Record type: `A` `AAAA` `CNAME` `MX` `NS` `PTR` `SRV` `TXT` |
| `--output` | `-o` | ❌ | — | Output file path (`.csv` or `.json`) |
| `--format` | | ❌ | `csv` | Output format: `csv` or `json` (auto-detected from extension) |
| `--show-all` | | ❌ | off | Print every query attempt, not just `FOUND` results |
| `--filter` | | ❌ | — | Only print lines with these statuses, e.g. `FOUND,TIMEOUT` |
| `--quiet` | `-q` | ❌ | off | Suppress per-query output; show only the final summary |
| `--threads` | `-t` | ❌ | `20` | Number of parallel threads |
| `--timeout` | | ❌ | `2.0` | Per-query timeout in seconds |
| `--lifetime` | | ❌ | `2.0` | Resolver lifetime in seconds |
| `--retries` | | ❌ | `2` | Retry count on `TIMEOUT` before giving up |
| `--rate-limit` | | ❌ | `0` | Max queries per second across all threads (`0` = unlimited) |

---

## Input File Format

Both input files use the same format: one entry per line. Empty lines and lines starting with `#` are ignored.

**`devices.txt`**
```
router01
switch-core
ap-floor2
# this line is ignored
firewall
```

**`domains.txt`**
```
corp.example.com
internal.example.net
# staging domain
staging.example.com
```

The script resolves every hostname × domain combination, e.g.:
- `router01.corp.example.com`
- `router01.internal.example.net`
- `router01.staging.example.com`
- `switch-core.corp.example.com`
- … and so on.

---

## Examples

### Basic A record resolution

```bash
python script-v0.2.py -d devices.txt -D domains.txt -s 10.0.0.1
```

### Query AAAA (IPv6) records

```bash
python script-v0.2.py -d devices.txt -D domains.txt -s 10.0.0.1 -r AAAA
```

### Query SRV records

```bash
python script-v0.2.py -d devices.txt -D domains.txt -s 10.0.0.1 -r SRV
```

### Save results to CSV

```bash
python script-v0.2.py -d devices.txt -D domains.txt -s 10.0.0.1 -o results.csv
```

### Save results to JSON

```bash
python script-v0.2.py -d devices.txt -D domains.txt -s 10.0.0.1 -o results.json
```

### Show all query attempts including failures

```bash
python script-v0.2.py -d devices.txt -D domains.txt -s 10.0.0.1 --show-all
```

### Show only FOUND and TIMEOUT results

```bash
python script-v0.2.py -d devices.txt -D domains.txt -s 10.0.0.1 --show-all --filter FOUND,TIMEOUT
```

### Quiet mode — summary only

```bash
python script-v0.2.py -d devices.txt -D domains.txt -s 10.0.0.1 -q
```

### Increase threads, set longer timeout, enable retries

```bash
python script-v0.2.py -d devices.txt -D domains.txt -s 10.0.0.1 -t 50 --timeout 5.0 --retries 3
```

### Rate-limit to 100 queries per second

```bash
python script-v0.2.py -d devices.txt -D domains.txt -s 10.0.0.1 --rate-limit 100
```

### Prompt for DNS server interactively (omit `-s`)

```bash
python script-v0.2.py -d devices.txt -D domains.txt
# Enter DNS server to query: _
```

---

## Output

### Terminal

Colour-coded output (automatically disabled when piped or redirected):

- 🟢 **Green** — `FOUND` results and matched hostnames
- 🔴 **Red** — `ERROR` and `NOT FOUND`
- 🟡 **Yellow** — `TIMEOUT`
- **Dim** — `NXDOMAIN` / `NOANSWER`

```
DNS server : 10.0.0.1
Record type: A
Devices    : 3
Domains    : 2
Total jobs : 6
Threads    : 20

[1/6] router01.corp.example.com (A) → 10.1.1.1
[2/6] switch-core.corp.example.com (A) → 10.1.1.2
[3/6] switch-core.internal.example.net (A) → 192.168.0.5
[4/6] ap-floor2.corp.example.com (A) → NXDOMAIN
...

=== SUMMARY BY HOSTNAME ===

router01:
  router01.corp.example.com (A) → 10.1.1.1
switch-core:
  switch-core.corp.example.com (A) → 10.1.1.2
  switch-core.internal.example.net (A) → 192.168.0.5
ap-floor2: NOT FOUND

=== STATS ===
  FOUND: 3
  NXDOMAIN: 2
  TIMEOUT: 1
  Total DNS queries sent (with retries): 7
```

### CSV (when `-o results.csv` is used)

| hostname | domain | fqdn | record_type | status | values | error | attempts |
|---|---|---|---|---|---|---|---|
| router01 | corp.example.com | router01.corp.example.com | A | FOUND | 10.1.1.1 | | 1 |
| switch-core | corp.example.com | switch-core.corp.example.com | A | FOUND | 10.1.1.2 | | 1 |
| ap-floor2 | corp.example.com | ap-floor2.corp.example.com | A | NXDOMAIN | | | 1 |

### JSON (when `-o results.json` is used)

```json
[
  {
    "fqdn": "router01.corp.example.com",
    "record_type": "A",
    "status": "FOUND",
    "values": ["10.1.1.1"],
    "error": "",
    "attempts": 1
  },
  ...
]
```

---

## Status Codes

| Status | Colour | Meaning |
|---|---|---|
| `FOUND` | 🟢 Green | Record(s) resolved successfully |
| `NXDOMAIN` | Dim | Domain does not exist |
| `NOANSWER` | Dim | Domain exists but has no record of the requested type |
| `TIMEOUT` | 🟡 Yellow | Query timed out after all retries |
| `ERROR` | 🔴 Red | Unexpected DNS or network error |

---

## Record Types

| Type | Output format in `values` |
|---|---|
| `A` | `10.1.1.1` |
| `AAAA` | `2001:db8::1` |
| `CNAME` | `target.example.com.` |
| `MX` | `10 mail.example.com.` *(priority + exchange)* |
| `NS` | `ns1.example.com.` |
| `PTR` | `hostname.example.com.` |
| `SRV` | `10 20 443 target.example.com.` *(priority weight port target)* |
| `TXT` | Raw text content |

---

## Notes

- The DNS server must be specified as a **valid IP address** — hostnames are rejected.
- Resolvers are **cached per thread** using `threading.local()` — no redundant object creation per query.
- On `TIMEOUT`, the query is **retried** up to `--retries` times before being recorded as failed. The `attempts` field in output reflects total tries.
- The progress bar (via `tqdm`) is shown automatically when `tqdm` is installed and `--show-all` is not active. Falls back gracefully if `tqdm` is not installed.
- ANSI colours are **automatically disabled** when stdout is not a TTY (e.g. when piping to a file or another command).
- Output files are **sorted alphabetically by FQDN**.
- The `--threads` default of `20` is conservative. For large inputs against a fast internal resolver, values of `50`–`100` are safe.
- Use `--rate-limit` to avoid hammering resolvers — especially useful for external or rate-sensitive servers.

---

## Part of `dnsweep`

This script is part of a growing collection of DNS utility tools. Planned additions:
- SRV record bulk queries
- DNS functionality checks (zone transfers, recursion tests, etc.)
- Multi-server comparison / diff tool

---

## License

MIT
