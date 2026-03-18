# Dnsweep-hostnames🔍

A fast, multi-threaded CLI tool for bulk DNS resolution — resolve hundreds of hostnames across multiple domains in seconds using a DNS server of your choice.

---

## Overview

`dnsweep` takes a list of **hostnames** and a list of **domains**, combines them into fully qualified domain names (FQDNs), and resolves each one against a specified DNS server in parallel. Results are printed to the terminal and optionally exported to a CSV file.

Useful for:
- Network audits and asset discovery
- Verifying DNS records across multiple domains
- Checking hostname presence in split-horizon DNS environments
- Bulk validation of DNS migrations

---

## Requirements

- Python 3.8+
- [`dnspython`](https://www.dnspython.org/)

Install the dependency:

```bash
pip install dnspython
```

---

## Usage

```bash
python dnsweep.py -d devices.txt -D domains.txt -s 192.168.1.1
```

### Arguments

| Argument | Short | Required | Description |
|---|---|---|---|
| `--devices` | `-d` | ✅ | Path to file with hostnames, one per line |
| `--domains` | `-D` | ✅ | Path to file with domains, one per line |
| `--server` | `-s` | ❌ | DNS server IP to query (prompted if omitted) |
| `--output` | `-o` | ❌ | Path to write CSV output file |
| `--threads` | `-t` | ❌ | Number of parallel threads (default: `20`) |
| `--timeout` | | ❌ | Per-query timeout in seconds (default: `2.0`) |
| `--lifetime` | | ❌ | Resolver lifetime in seconds (default: `2.0`) |
| `--show-all` | | ❌ | Print every query attempt, not just resolved ones |

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

The script will resolve every combination, e.g.:
- `router01.corp.example.com`
- `router01.internal.example.net`
- `router01.staging.example.com`
- `switch-core.corp.example.com`
- … and so on.

---

## Examples

### Basic resolution, print found results only

```bash
python dnsweep.py -d devices.txt -D domains.txt -s 10.0.0.1
```

### Save results to CSV

```bash
python dnsweep.py -d devices.txt -D domains.txt -s 10.0.0.1 -o results.csv
```

### Show all query attempts (including failures)

```bash
python dnsweep.py -d devices.txt -D domains.txt -s 10.0.0.1 --show-all
```

### Increase threads and set a longer timeout

```bash
python dnsweep.py -d devices.txt -D domains.txt -s 10.0.0.1 -t 50 --timeout 5.0
```

### Prompt for DNS server interactively (omit `-s`)

```bash
python dnsweep.py -d devices.txt -D domains.txt
# Enter DNS server to query: _
```

---

## Output

### Terminal

```
Using DNS server: 10.0.0.1
Devices: 3
Domains: 2
Total queries: 6
Threads: 20

=== SUMMARY BY HOSTNAME ===

router01:
  router01.corp.example.com -> 10.1.1.1
switch-core:
  switch-core.corp.example.com -> 10.1.1.2
  switch-core.internal.example.net -> 192.168.0.5
ap-floor2: NOT FOUND

=== STATS ===
ERROR: 0
FOUND: 3
NXDOMAIN: 2
TIMEOUT: 1
```

### CSV (when `--output` is used)

| hostname | domain | fqdn | status | ip_addresses | error |
|---|---|---|---|---|---|
| router01 | corp.example.com | router01.corp.example.com | FOUND | 10.1.1.1 | |
| switch-core | corp.example.com | switch-core.corp.example.com | FOUND | 10.1.1.2 | |
| ap-floor2 | corp.example.com | ap-floor2.corp.example.com | NXDOMAIN | | |

---

## Status Codes

| Status | Meaning |
|---|---|
| `FOUND` | A record(s) resolved successfully |
| `NXDOMAIN` | Domain does not exist |
| `NOANSWER` | Domain exists but has no A record |
| `TIMEOUT` | Query timed out |
| `ERROR` | Unexpected DNS or network error |

---

## Notes

- Only **A records** are queried. AAAA, CNAME, SRV, etc. are not resolved (planned for future scripts in this repo).
- Each query uses a **fresh resolver instance** per thread — no shared state between threads.
- Results in the CSV are sorted alphabetically by FQDN.
- The `--threads` default of `20` is conservative. For large inputs against a fast internal resolver, values of `50`–`100` are safe.

---

## Part of `dnsweep`

This script is part of a growing collection of DNS utility tools. Planned additions:
- SRV record bulk queries
- DNS functionality checks (zone transfers, recursion tests, etc.)
- Multi-server comparison / diff tool

---

## License

MIT
