#!/usr/bin/env python3

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys

import dns.exception
import dns.resolver


def load_lines(filename):
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


def build_resolver(dns_server, timeout=2.0, lifetime=2.0):
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = [dns_server]
    resolver.timeout = timeout
    resolver.lifetime = lifetime
    return resolver


def resolve_fqdn(fqdn, dns_server, timeout=2.0, lifetime=2.0):
    resolver = build_resolver(dns_server, timeout=timeout, lifetime=lifetime)

    try:
        answers = resolver.resolve(fqdn, "A")
        ips = sorted({r.address for r in answers})
        return {
            "fqdn": fqdn,
            "status": "FOUND",
            "ips": ips,
            "error": "",
        }

    except dns.resolver.NXDOMAIN:
        return {
            "fqdn": fqdn,
            "status": "NXDOMAIN",
            "ips": [],
            "error": "",
        }

    except dns.resolver.NoAnswer:
        return {
            "fqdn": fqdn,
            "status": "NOANSWER",
            "ips": [],
            "error": "",
        }

    except dns.resolver.Timeout:
        return {
            "fqdn": fqdn,
            "status": "TIMEOUT",
            "ips": [],
            "error": "",
        }

    except dns.exception.DNSException as exc:
        return {
            "fqdn": fqdn,
            "status": "ERROR",
            "ips": [],
            "error": str(exc),
        }

    except Exception as exc:
        return {
            "fqdn": fqdn,
            "status": "ERROR",
            "ips": [],
            "error": str(exc),
        }


def split_fqdn(fqdn):
    parts = fqdn.split(".", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return fqdn, ""


def write_csv(output_file, rows):
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["hostname", "domain", "fqdn", "status", "ip_addresses", "error"])

        for row in rows:
            hostname, domain = split_fqdn(row["fqdn"])
            writer.writerow([
                hostname,
                domain,
                row["fqdn"],
                row["status"],
                ",".join(row["ips"]),
                row["error"],
            ])


def main():
    parser = argparse.ArgumentParser(
        description="Resolve hostnames against multiple domains using a chosen DNS server."
    )

    parser.add_argument("-d", "--devices", required=True, help="File with hostnames, one per line")
    parser.add_argument("-D", "--domains", required=True, help="File with domains, one per line")
    parser.add_argument("-s", "--server", help="DNS server to query")
    parser.add_argument("-o", "--output", help="Optional CSV output file")
    parser.add_argument("-t", "--threads", type=int, default=20, help="Number of parallel threads (default: 20)")
    parser.add_argument("--timeout", type=float, default=2.0, help="Per-query timeout in seconds (default: 2.0)")
    parser.add_argument("--lifetime", type=float, default=2.0, help="Resolver lifetime in seconds (default: 2.0)")
    parser.add_argument("--show-all", action="store_true", help="Show all attempts, not only found results")

    args = parser.parse_args()

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

    dns_server = args.server
    if not dns_server:
        dns_server = input("Enter DNS server to query: ").strip()

    if not dns_server:
        print("ERROR: no DNS server provided", file=sys.stderr)
        sys.exit(1)

    jobs = []
    for hostname in devices:
        for domain in domains:
            fqdn = f"{hostname}.{domain}"
            jobs.append((hostname, domain, fqdn))

    total = len(jobs)
    print(f"\nUsing DNS server: {dns_server}")
    print(f"Devices: {len(devices)}")
    print(f"Domains: {len(domains)}")
    print(f"Total queries: {total}")
    print(f"Threads: {args.threads}")
    print("")

    all_rows = []
    found_by_hostname = {hostname: [] for hostname in devices}

    completed = 0

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        future_map = {
            executor.submit(
                resolve_fqdn,
                fqdn,
                dns_server,
                args.timeout,
                args.lifetime,
            ): (hostname, domain, fqdn)
            for hostname, domain, fqdn in jobs
        }

        for future in as_completed(future_map):
            hostname, domain, fqdn = future_map[future]
            completed += 1

            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "fqdn": fqdn,
                    "status": "ERROR",
                    "ips": [],
                    "error": str(exc),
                }

            all_rows.append(result)

            if result["status"] == "FOUND":
                found_by_hostname[hostname].append(result)

            if args.show_all:
                if result["status"] == "FOUND":
                    print(f"[{completed}/{total}] {result['fqdn']} -> {', '.join(result['ips'])}")
                elif result["error"]:
                    print(f"[{completed}/{total}] {result['fqdn']} -> {result['status']} ({result['error']})")
                else:
                    print(f"[{completed}/{total}] {result['fqdn']} -> {result['status']}")

    print("\n=== SUMMARY BY HOSTNAME ===\n")

    for hostname in devices:
        matches = sorted(found_by_hostname[hostname], key=lambda x: x["fqdn"])

        if matches:
            print(f"{hostname}:")
            for match in matches:
                print(f"  {match['fqdn']} -> {', '.join(match['ips'])}")
        else:
            print(f"{hostname}: NOT FOUND")

    status_counts = {}
    for row in all_rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1

    print("\n=== STATS ===")
    for status in sorted(status_counts):
        print(f"{status}: {status_counts[status]}")

    if args.output:
        try:
            all_rows_sorted = sorted(all_rows, key=lambda x: x["fqdn"])
            write_csv(args.output, all_rows_sorted)
            print(f"\nCSV written to: {args.output}")
        except Exception as exc:
            print(f"\nERROR writing CSV: {exc}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
