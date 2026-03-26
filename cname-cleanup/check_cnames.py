#!/usr/bin/env python3

import argparse
import csv
import sys
import dns.resolver
import dns.exception


def build_resolver(server=None, timeout=3.0, lifetime=5.0):
    resolver = dns.resolver.Resolver()
    resolver.timeout = timeout
    resolver.lifetime = lifetime
    if server:
        resolver.nameservers = [server]
    return resolver


def normalize_fqdn(name):
    return name.strip().rstrip(".")


def safe_resolve(resolver, name, rtype):
    try:
        answers = resolver.resolve(name, rtype)
        return "OK", [str(r).rstrip(".") for r in answers], ""
    except dns.resolver.NXDOMAIN:
        return "NXDOMAIN", [], "NXDOMAIN"
    except dns.resolver.NoAnswer:
        return "NOANSWER", [], "NoAnswer"
    except dns.resolver.Timeout:
        return "TIMEOUT", [], "Timeout"
    except dns.exception.DNSException as e:
        return "ERROR", [], str(e)


def check_name(resolver, name):
    name = normalize_fqdn(name)

    cname_status, cname_answers, cname_error = safe_resolve(resolver, name, "CNAME")
    a_status, a_answers, a_error = safe_resolve(resolver, name, "A")
    aaaa_status, aaaa_answers, aaaa_error = safe_resolve(resolver, name, "AAAA")

    canonical = cname_answers[0] if cname_answers else ""

    target_a_status = ""
    target_a_answers = []
    target_a_error = ""

    target_aaaa_status = ""
    target_aaaa_answers = []
    target_aaaa_error = ""

    if canonical:
        target_a_status, target_a_answers, target_a_error = safe_resolve(resolver, canonical, "A")
        target_aaaa_status, target_aaaa_answers, target_aaaa_error = safe_resolve(resolver, canonical, "AAAA")

    if cname_status == "NXDOMAIN":
        overall_status = "NXDOMAIN"
    elif cname_answers and (a_answers or aaaa_answers):
        overall_status = "OK"
    elif cname_answers and not (a_answers or aaaa_answers):
        overall_status = "BROKEN_CNAME"
    elif not cname_answers and (a_answers or aaaa_answers):
        overall_status = "NOT_A_CNAME_HAS_ADDRESS"
    elif cname_status == "NOANSWER" and a_status == "NOANSWER" and aaaa_status == "NOANSWER":
        overall_status = "NO_RECORDS"
    elif "TIMEOUT" in (cname_status, a_status, aaaa_status):
        overall_status = "DNS_TIMEOUT"
    elif "ERROR" in (cname_status, a_status, aaaa_status):
        overall_status = "DNS_ERROR"
    else:
        overall_status = "UNRESOLVED"

    return {
        "name": name,
        "canonical": canonical,
        "overall_status": overall_status,
        "cname_status": cname_status,
        "cname_answers": ";".join(cname_answers),
        "a_status": a_status,
        "a_answers": ";".join(a_answers),
        "aaaa_status": aaaa_status,
        "aaaa_answers": ";".join(aaaa_answers),
        "target_a_status": target_a_status,
        "target_a_answers": ";".join(target_a_answers),
        "target_aaaa_status": target_aaaa_status,
        "target_aaaa_answers": ";".join(target_aaaa_answers),
        "errors": " | ".join(
            x for x in [
                cname_error, a_error, aaaa_error, target_a_error, target_aaaa_error
            ] if x
        ),
    }


def read_input_file(input_file):
    names = []

    with open(input_file, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            raw = line.strip()

            if not raw:
                continue

            if raw.startswith("#"):
                continue

            names.append({
                "line_number": line_number,
                "name": raw
            })

    if not names:
        raise ValueError("Input file is empty or contains only comments/blank lines")

    return names


def write_output_csv(output_file, results):
    if not results:
        return

    fieldnames = list(results[0].keys())

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


def main():
    parser = argparse.ArgumentParser(
        description="Check plain text FQDN list and identify broken CNAMEs"
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Input text file, one FQDN per line"
    )
    parser.add_argument(
        "-o", "--output",
        default="cnames_checked.csv",
        help="Output CSV file (default: cnames_checked.csv)"
    )
    parser.add_argument(
        "-s", "--server",
        help="DNS server to query, e.g. 172.20.1.53"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Per-query timeout in seconds (default: 3.0)"
    )
    parser.add_argument(
        "--lifetime",
        type=float,
        default=5.0,
        help="Resolver lifetime in seconds (default: 5.0)"
    )
    args = parser.parse_args()

    try:
        resolver = build_resolver(
            server=args.server,
            timeout=args.timeout,
            lifetime=args.lifetime
        )

        names = read_input_file(args.input)
        results = []
        total = len(names)

        for idx, item in enumerate(names, start=1):
            name = item["name"]

            result = check_name(resolver, name)
            result["line_number"] = item["line_number"]

            ordered_result = {
                "line_number": result["line_number"],
                "name": result["name"],
                "canonical": result["canonical"],
                "overall_status": result["overall_status"],
                "cname_status": result["cname_status"],
                "cname_answers": result["cname_answers"],
                "a_status": result["a_status"],
                "a_answers": result["a_answers"],
                "aaaa_status": result["aaaa_status"],
                "aaaa_answers": result["aaaa_answers"],
                "target_a_status": result["target_a_status"],
                "target_a_answers": result["target_a_answers"],
                "target_aaaa_status": result["target_aaaa_status"],
                "target_aaaa_answers": result["target_aaaa_answers"],
                "errors": result["errors"],
            }

            results.append(ordered_result)
            print(f"[{idx}/{total}] {name} : {ordered_result['overall_status']}")

        write_output_csv(args.output, results)
        print(f"[INFO] Results written to {args.output}")

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
