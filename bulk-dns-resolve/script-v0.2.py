#!/usr/bin/env python3
"""
dnsweep.py — Bulk DNS resolver for hostnames across multiple domains.

Part of the dnsweep toolkit: https://github.com/yourname/dnsweep
"""

import argparse
import csv
import ipaddress
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import dns.exception
import dns.resolver

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

# ---------------------------------------------------------------------------
# ANSI colours (disabled automatically when not a TTY)
# ---------------------------------------------------------------------------

class Colour:
    _enabled = sys.stdout.isatty()

    GREEN  = "\033[32m"   if _enabled else ""
    RED    = "\033[31m"   if _enabled else ""
    YELLOW = "\033[33m"   if _enabled else ""
    CYAN   = "\033[36m"   if _enabled else ""
    DIM    = "\033[2m"    if _enabled else ""
    RESET  = "\033[0m"    if _enabled else ""

    @classmethod
    def green(cls, s):  return f"{cls.GREEN}{s}{cls.RESET}"
    @classmethod
    def red(cls, s):    return f"{cls.RED}{s}{cls.RESET}"
    @classmethod
    def yellow(cls, s): return f"{cls.YELLOW}{s}{cls.RESET}"
    @classmethod
    def cyan(cls, s):   return f"{cls.CYAN}{s}{cls.RESET}"
    @classmethod
    def dim(cls, s):    return f"{cls.DIM}{s}{cls.RESET}"


STATUS_COLOUR = {
    "FOUND":    Colour.green,
    "NXDOMAIN": Colour.dim,
    "NOANSWER": Colour.dim,
    "TIMEOUT":  Colour.yellow,
    "ERROR":    Colour.red,
}

VALID_RECORD_TYPES = {"A", "AAAA", "CNAME", "MX", "PTR", "TXT", "NS", "SRV"}

# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_lines(filename: str) -> list[str]:
    path = Path(filename)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filename}")
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def validate_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def split_fqdn(fqdn: str) -> tuple[str, str]:
    """Split 'host.domain.tld' → ('host', 'domain.tld').
    Returns (fqdn, '') for bare names with no dot."""
    parts = fqdn.split(".", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (fqdn, "")


# ---------------------------------------------------------------------------
# Thread-local resolver pool
# ---------------------------------------------------------------------------

_thread_local = threading.local()


def get_resolver(dns_server: str, timeout: float, lifetime: float) -> dns.resolver.Resolver:
    """Return a per-thread cached resolver, creating it on first use."""
    if not hasattr(_thread_local, "resolver"):
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = [dns_server]
        resolver.timeout = timeout
        resolver.lifetime = lifetime
        _thread_local.resolver = resolver
    return _thread_local.resolver


# ---------------------------------------------------------------------------
# Core resolution
# ---------------------------------------------------------------------------

def resolve_fqdn(
    fqdn: str,
    dns_server: str,
    record_type: str = "A",
    timeout: float = 2.0,
    lifetime: float = 2.0,
    retries: int = 2,
) -> dict:
    """Resolve a single FQDN, retrying on TIMEOUT up to *retries* times."""
    resolver = get_resolver(dns_server, timeout, lifetime)
    attempt = 0

    while True:
        attempt += 1
        try:
            answers = resolver.resolve(fqdn, record_type)
            values = _extract_values(answers, record_type)
            return {
                "fqdn": fqdn,
                "record_type": record_type,
                "status": "FOUND",
                "values": values,
                "error": "",
                "attempts": attempt,
            }

        except dns.resolver.NXDOMAIN:
            return _err(fqdn, record_type, "NXDOMAIN", attempt=attempt)

        except dns.resolver.NoAnswer:
            return _err(fqdn, record_type, "NOANSWER", attempt=attempt)

        except dns.resolver.Timeout:
            if attempt <= retries:
                continue
            return _err(fqdn, record_type, "TIMEOUT", attempt=attempt)

        except dns.exception.DNSException as exc:
            return _err(fqdn, record_type, "ERROR", str(exc), attempt=attempt)

        except Exception as exc:
            return _err(fqdn, record_type, "ERROR", str(exc), attempt=attempt)


def _extract_values(answers, record_type: str) -> list[str]:
    """Pull the relevant string value out of each RRset record."""
    out = []
    for r in answers:
        rtype = record_type.upper()
        if rtype == "A":
            out.append(r.address)
        elif rtype == "AAAA":
            out.append(r.address)
        elif rtype == "CNAME":
            out.append(str(r.target))
        elif rtype == "MX":
            out.append(f"{r.preference} {r.exchange}")
        elif rtype in ("PTR", "NS"):
            out.append(str(r.target))
        elif rtype == "TXT":
            out.append(b" ".join(r.strings).decode("utf-8", errors="replace"))
        elif rtype == "SRV":
            out.append(f"{r.priority} {r.weight} {r.port} {r.target}")
        else:
            out.append(str(r))
    return sorted(set(out))


def _err(fqdn, record_type, status, error="", attempt=1) -> dict:
    return {
        "fqdn": fqdn,
        "record_type": record_type,
        "status": status,
        "values": [],
        "error": error,
        "attempts": attempt,
    }


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_csv(output_file: str, rows: list[dict]) -> None:
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "hostname", "domain", "fqdn", "record_type",
            "status", "values", "error", "attempts",
        ])
        for row in rows:
            hostname, domain = split_fqdn(row["fqdn"])
            writer.writerow([
                hostname,
                domain,
                row["fqdn"],
                row["record_type"],
                row["status"],
                ",".join(row["values"]),
                row["error"],
                row["attempts"],
            ])


def write_json(output_file: str, rows: list[dict]) -> None:
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


# ---------------------------------------------------------------------------
# Printing helpers
# ---------------------------------------------------------------------------

def print_result_line(result: dict, completed: int, total: int, quiet: bool) -> None:
    if quiet:
        return

    status = result["status"]
    colour_fn = STATUS_COLOUR.get(status, lambda s: s)
    prefix = Colour.dim(f"[{completed}/{total}]")
    fqdn = result["fqdn"]
    rtype = result["record_type"]

    if status == "FOUND":
        vals = ", ".join(result["values"])
        print(f"{prefix} {fqdn} ({rtype}) {Colour.dim('→')} {colour_fn(vals)}")
    elif result["error"]:
        print(f"{prefix} {fqdn} ({rtype}) {Colour.dim('→')} {colour_fn(status)} ({result['error']})")
    else:
        print(f"{prefix} {fqdn} ({rtype}) {Colour.dim('→')} {colour_fn(status)}")


def print_summary(devices: list[str], found_by_hostname: dict, all_rows: list[dict], quiet: bool) -> None:
    if not quiet:
        print(f"\n{Colour.cyan('=== SUMMARY BY HOSTNAME ===')} \n")

    for hostname in devices:
        matches = sorted(found_by_hostname[hostname], key=lambda x: x["fqdn"])
        if matches:
            print(Colour.green(f"{hostname}:"))
            for m in matches:
                vals = ", ".join(m["values"])
                print(f"  {m['fqdn']} ({m['record_type']}) → {vals}")
        else:
            print(f"{hostname}: {Colour.red('NOT FOUND')}")

    status_counts: dict[str, int] = {}
    total_attempts = 0
    for row in all_rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        total_attempts += row["attempts"]

    print(f"\n{Colour.cyan('=== STATS ===')} ")
    for status in sorted(status_counts):
        colour_fn = STATUS_COLOUR.get(status, lambda s: s)
        print(f"  {colour_fn(status)}: {status_counts[status]}")
    print(f"  Total DNS queries sent (with retries): {total_attempts}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "dnsweep — resolve hostnames across multiple domains using a chosen DNS server.\n"
            "Part of the dnsweep toolkit."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  %(prog)s -d devices.txt -D domains.txt -s 10.0.0.1
  %(prog)s -d devices.txt -D domains.txt -s 10.0.0.1 -o results.csv
  %(prog)s -d devices.txt -D domains.txt -s 10.0.0.1 --record-type AAAA
  %(prog)s -d devices.txt -D domains.txt -s 10.0.0.1 --show-all --filter FOUND,TIMEOUT
  %(prog)s -d devices.txt -D domains.txt -s 10.0.0.1 -o out.json --format json
        """,
    )

    # Required
    parser.add_argument("-d", "--devices", required=True,
                        help="File with hostnames, one per line")
    parser.add_argument("-D", "--domains", required=True,
                        help="File with domains, one per line")

    # DNS
    parser.add_argument("-s", "--server",
                        help="DNS server IP to query (prompted if omitted)")
    parser.add_argument("-r", "--record-type", default="A",
                        metavar="TYPE",
                        help=f"Record type to query. Supported: {', '.join(sorted(VALID_RECORD_TYPES))} (default: A)")

    # Output
    parser.add_argument("-o", "--output",
                        help="Output file path (.csv or .json)")
    parser.add_argument("--format", choices=["csv", "json"], default="csv",
                        help="Output format when -o is given (default: csv)")
    parser.add_argument("--show-all", action="store_true",
                        help="Print every query attempt, not just FOUND results")
    parser.add_argument("--filter", metavar="STATUS[,STATUS]",
                        help="Only print lines matching these statuses, e.g. FOUND,TIMEOUT")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Suppress per-query output; print only the final summary")

    # Performance
    parser.add_argument("-t", "--threads", type=int, default=20,
                        help="Number of parallel threads (default: 20)")
    parser.add_argument("--timeout", type=float, default=2.0,
                        help="Per-query timeout in seconds (default: 2.0)")
    parser.add_argument("--lifetime", type=float, default=2.0,
                        help="Resolver lifetime in seconds (default: 2.0)")
    parser.add_argument("--retries", type=int, default=2,
                        help="Retry count for TIMEOUT results before giving up (default: 2)")
    parser.add_argument("--rate-limit", type=float, default=0.0, metavar="QPS",
                        help="Max queries per second across all threads (0 = unlimited)")

    return parser


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Simple token-bucket rate limiter."""

    def __init__(self, qps: float):
        self.enabled = qps > 0
        self._interval = 1.0 / qps if qps > 0 else 0.0
        self._lock = threading.Lock()
        self._last = 0.0

    def acquire(self):
        if not self.enabled:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._interval - (now - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = build_parser()
    args = parser.parse_args()

    # Validate record type
    record_type = args.record_type.upper()
    if record_type not in VALID_RECORD_TYPES:
        print(
            f"ERROR: unsupported record type '{record_type}'. "
            f"Choose from: {', '.join(sorted(VALID_RECORD_TYPES))}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load input files
    try:
        devices = load_lines(args.devices)
        domains = load_lines(args.domains)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if not devices:
        print("ERROR: devices file is empty", file=sys.stderr)
        sys.exit(1)
    if not domains:
        print("ERROR: domains file is empty", file=sys.stderr)
        sys.exit(1)

    # DNS server
    dns_server = args.server
    if not dns_server:
        dns_server = input("Enter DNS server to query: ").strip()
    if not dns_server:
        print("ERROR: no DNS server provided", file=sys.stderr)
        sys.exit(1)
    if not validate_ip(dns_server):
        print(f"ERROR: '{dns_server}' does not look like a valid IP address", file=sys.stderr)
        sys.exit(1)

    # Status filter
    filter_statuses: set[str] | None = None
    if args.filter:
        filter_statuses = {s.strip().upper() for s in args.filter.split(",")}

    # Build job list
    jobs = [
        (hostname, domain, f"{hostname}.{domain}")
        for hostname in devices
        for domain in domains
    ]
    total = len(jobs)

    # Header
    if not args.quiet:
        print(f"\n{Colour.cyan('DNS server :')} {dns_server}")
        print(f"{Colour.cyan('Record type:')} {record_type}")
        print(f"{Colour.cyan('Devices    :')} {len(devices)}")
        print(f"{Colour.cyan('Domains    :')} {len(domains)}")
        print(f"{Colour.cyan('Total jobs :')} {total}")
        print(f"{Colour.cyan('Threads    :')} {args.threads}")
        if args.rate_limit > 0:
            print(f"{Colour.cyan('Rate limit :')} {args.rate_limit} QPS")
        print()

    # Run
    all_rows: list[dict] = []
    found_by_hostname: dict[str, list] = {h: [] for h in devices}
    rate_limiter = RateLimiter(args.rate_limit)
    completed = 0

    use_progress = TQDM_AVAILABLE and not args.show_all and not args.quiet
    progress = tqdm(total=total, unit="query", ncols=80) if use_progress else None

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        future_map = {}
        for hostname, domain, fqdn in jobs:
            rate_limiter.acquire()
            future = executor.submit(
                resolve_fqdn,
                fqdn,
                dns_server,
                record_type,
                args.timeout,
                args.lifetime,
                args.retries,
            )
            future_map[future] = (hostname, domain, fqdn)

        for future in as_completed(future_map):
            hostname, domain, fqdn = future_map[future]
            completed += 1

            try:
                result = future.result()
            except Exception as exc:
                result = _err(fqdn, record_type, "ERROR", str(exc))

            all_rows.append(result)

            if result["status"] == "FOUND":
                found_by_hostname[hostname].append(result)

            # Per-line output
            if args.show_all or result["status"] == "FOUND":
                show = True
                if filter_statuses and result["status"] not in filter_statuses:
                    show = False
                if show:
                    print_result_line(result, completed, total, args.quiet)

            if progress:
                progress.update(1)

    if progress:
        progress.close()

    print_summary(devices, found_by_hostname, all_rows, quiet=False)

    # Write output file
    if args.output:
        all_rows_sorted = sorted(all_rows, key=lambda x: x["fqdn"])
        try:
            fmt = args.format
            # Auto-detect format from extension if not explicitly set
            if args.output.endswith(".json"):
                fmt = "json"
            elif args.output.endswith(".csv"):
                fmt = "csv"

            if fmt == "json":
                write_json(args.output, all_rows_sorted)
            else:
                write_csv(args.output, all_rows_sorted)

            print(f"\n{Colour.green('Output written to:')} {args.output}")
        except Exception as exc:
            print(f"\nERROR writing output: {exc}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
