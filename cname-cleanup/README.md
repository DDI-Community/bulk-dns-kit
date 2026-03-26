# CNAME Checker Tools

Two scripts for validating a list of FQDNs/CNAMEs and identifying broken ones — those that do not eventually resolve to an A/AAAA record.

---

## Scripts

| Script | Language | Key strength |
|---|---|---|
| `check_cnames.sh` | Bash | Lightweight, no dependencies beyond `dig` |
| `check_cnames.py` | Python | Detailed per-record breakdown, richer status codes |

Both scripts accept the same input format and produce CSV output suitable for further processing.

---

## Input file format

One FQDN per line. Lines starting with `#` and blank lines are ignored.

```
www.example.com
api.example.com
# this entry is disabled
old.legacy.example.com
```

---

## check_cnames.sh

### Requirements

- `dig` (part of `dnsutils` on Debian/Ubuntu, `bind` via Homebrew on macOS)

```bash
# Debian/Ubuntu
sudo apt install dnsutils

# macOS
brew install bind
```

### Usage

```bash
chmod +x check_cnames.sh

# Basic — prints only broken/error entries to terminal
./check_cnames.sh cnames.txt

# Verbose — also prints OK entries to terminal
./check_cnames.sh cnames.txt --verbose

# Custom DNS server
./check_cnames.sh cnames.txt --dns 8.8.8.8

# Save full results to CSV
./check_cnames.sh cnames.txt --output results.csv

# All options combined
./check_cnames.sh cnames.txt --dns 1.1.1.1 --output results.csv --verbose
```

### Output

Always written regardless of `--verbose`:
- `ok_cnames_<timestamp>.txt` — plain list of resolving entries
- `broken_cnames_<timestamp>.txt` — plain list of broken/errored entries
- `<file>.csv` (if `--output` is specified) — full structured report

#### CSV columns

| Column | Description |
|---|---|
| `cname` | The input FQDN |
| `status` | `OK`, `BROKEN`, or `ERROR` |
| `resolved_ip` | Final IP if resolved, last answer if broken, empty if error |
| `checked_at` | ISO 8601 timestamp of the check |

#### Status codes

| Status | Meaning |
|---|---|
| `OK` | Resolved to an IPv4 or IPv6 address |
| `BROKEN` | Got a response but it did not end in an IP (dangling CNAME chain) |
| `ERROR` | No response at all — timeout, NXDOMAIN, or `dig` failure |

---

## check_cnames.py

### Requirements

- Python 3.7+
- [`dnspython`](https://www.dnspython.org/)

```bash
pip install dnspython
```

### Usage

```bash
# Basic
python check_cnames.py -i cnames.txt

# Custom output file
python check_cnames.py -i cnames.txt -o results.csv

# Custom DNS server
python check_cnames.py -i cnames.txt -s 8.8.8.8

# Adjust timeouts
python check_cnames.py -i cnames.txt --timeout 2.0 --lifetime 4.0

# All options combined
python check_cnames.py -i cnames.txt -s 172.20.1.53 -o results.csv --timeout 2.0 --lifetime 4.0
```

### Options

| Flag | Default | Description |
|---|---|---|
| `-i`, `--input` | *(required)* | Input file path |
| `-o`, `--output` | `cnames_checked.csv` | Output CSV file path |
| `-s`, `--server` | system default | DNS server IP to query |
| `--timeout` | `3.0` | Per-query timeout in seconds |
| `--lifetime` | `5.0` | Resolver lifetime in seconds |

### Output

Results are written to the CSV specified by `--output`. Progress is printed to stdout as each entry is processed.

#### CSV columns

| Column | Description |
|---|---|
| `line_number` | Line number in the input file |
| `name` | The input FQDN (normalised) |
| `canonical` | CNAME target if a CNAME record exists |
| `overall_status` | High-level result (see status codes below) |
| `cname_status` | Raw result of the CNAME query |
| `cname_answers` | CNAME record value(s) |
| `a_status` | Raw result of the A query |
| `a_answers` | A record value(s) |
| `aaaa_status` | Raw result of the AAAA query |
| `aaaa_answers` | AAAA record value(s) |
| `target_a_status` | A query result on the CNAME target |
| `target_a_answers` | A record value(s) for the CNAME target |
| `target_aaaa_status` | AAAA query result on the CNAME target |
| `target_aaaa_answers` | AAAA record value(s) for the CNAME target |
| `errors` | Any error messages, pipe-separated |

#### Status codes

| Status | Meaning |
|---|---|
| `OK` | CNAME exists and resolves to at least one A/AAAA record |
| `BROKEN_CNAME` | CNAME exists but does not resolve to any address |
| `NXDOMAIN` | Domain does not exist |
| `NOT_A_CNAME_HAS_ADDRESS` | No CNAME record, but A/AAAA records exist directly |
| `NO_RECORDS` | No CNAME, A, or AAAA records found |
| `DNS_TIMEOUT` | One or more queries timed out |
| `DNS_ERROR` | A DNS exception occurred |
| `UNRESOLVED` | Did not match any of the above conditions |

---

## Choosing a script

Use **`check_cnames.sh`** if you want a quick, dependency-free check and only need to know whether something resolves or not.

Use **`check_cnames.py`** if you need detailed diagnostics per record — e.g. distinguishing a dangling CNAME from an NXDOMAIN, or inspecting what each step of the chain returned.
