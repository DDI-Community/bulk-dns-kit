# check_dns.sh

Batch DNS forward (A) and reverse (PTR) resolution checker. Reads a list of FQDN + IP pairs from a text file and verifies both directions, with colour-coded output and a summary.

## Requirements

- `bash` 4+
- `dig` — `bind-utils` (RHEL/CentOS) or `dnsutils` (Debian/Ubuntu)

## Usage

```bash
chmod +x check_dns.sh

# Using system resolver
./check_dns.sh <input_file>

# Using a specific DNS server
./check_dns.sh <input_file> <resolver_ip>
```

## Input file format

One entry per line: `<fqdn> <ip>`. Blank lines and `#` comments are ignored.

```
# Production
test1.example.com  192.168.12.10
test2.example.com  192.168.12.11

# Dev
dev1.example.com   10.0.0.5
```

## Output

| Column | Description |
|--------|-------------|
| FQDN | Name from the input file |
| Expected IP | IP from the input file |
| A record | Forward resolution result vs. expected IP |
| PTR record | Reverse resolution result vs. expected FQDN |

Each result is colour-coded:

- 🟢 `OK` — matches expected value
- 🟡 `MISMATCH` — resolved, but to a different value
- 🔴 `NXDOMAIN` — no answer returned

A summary line at the end shows total counts per state.

## Example

```
$ ./check_dns.sh hosts.txt 192.168.1.53

DNS Resolution Check
Input file : hosts.txt
Resolver   : 192.168.1.53

FQDN                                          Expected IP        A record                            PTR record
───────────────────────────────────────────────────────────────────────────────────────────────────────────────
test1.example.com                             192.168.12.10      OK (192.168.12.10)                  OK (test1.example.com)
test2.example.com                             192.168.12.11      MISMATCH (192.168.12.99)            OK (test2.example.com)

Summary:  Total: 2  |  OK: 1  |  Mismatch: 1  |  Failed: 0
```
