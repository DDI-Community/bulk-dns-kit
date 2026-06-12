#!/usr/bin/env bash
# check_dns.sh — Forward (A) and reverse (PTR) DNS resolution checker
# Usage: ./check_dns.sh <input_file> [resolver]
# Input file format: <fqdn> <ip>  (one per line, blank lines and # comments ignored)

INPUT="${1}"
RESOLVER="${2:-}"  # optional: e.g. 8.8.8.8 or your internal DNS

# ── colours ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

# ── helpers ────────────────────────────────────────────────────────────────────
usage() {
    echo "Usage: $0 <input_file> [resolver_ip]"
    echo "  input_file   — file with lines: <fqdn> <ip>"
    echo "  resolver_ip  — optional DNS server to query (default: system resolver)"
    exit 1
}

dig_cmd() {
    # Returns: dig [@resolver] "$@" +short +time=3 +tries=1
    if [[ -n "$RESOLVER" ]]; then
        dig "@${RESOLVER}" "$@" +short +time=3 +tries=1
    else
        dig "$@" +short +time=3 +tries=1
    fi
}

status_label() {
    local result="$1" expected="$2"
    if [[ -z "$result" ]]; then
        echo -e "${RED}NXDOMAIN / no answer${RESET}"
    elif [[ "$result" == "$expected" ]]; then
        echo -e "${GREEN}OK${RESET}  ($result)"
    else
        echo -e "${YELLOW}MISMATCH${RESET}  got: $result  expected: $expected"
    fi
}

# ── pre-flight ─────────────────────────────────────────────────────────────────
[[ -z "$INPUT" ]] && usage
[[ ! -f "$INPUT" ]] && { echo "Error: file '$INPUT' not found."; exit 1; }
command -v dig &>/dev/null || { echo "Error: 'dig' not found. Install bind-utils / dnsutils."; exit 1; }

resolver_label="${RESOLVER:-system default}"
echo -e "${BOLD}DNS Resolution Check${RESET}"
echo -e "Input file : ${CYAN}${INPUT}${RESET}"
echo -e "Resolver   : ${CYAN}${resolver_label}${RESET}"
[[ -n "$RESOLVER" ]] && echo -e "Server IP  : ${CYAN}${RESOLVER}${RESET}"
echo

# ── counters ───────────────────────────────────────────────────────────────────
total=0; ok=0; mismatch=0; fail=0

# ── header ─────────────────────────────────────────────────────────────────────
printf "${BOLD}%-45s %-18s %-35s %-35s${RESET}\n" \
    "FQDN" "Expected IP" "A record" "PTR record"
printf '%s\n' "$(printf '%.0s─' {1..135})"

# ── main loop ──────────────────────────────────────────────────────────────────
while IFS= read -r line; do
    # skip blank lines and comments
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

    fqdn=$(awk '{print $1}' <<< "$line")
    ip=$(awk '{print $2}' <<< "$line")

    [[ -z "$fqdn" || -z "$ip" ]] && continue
    (( total++ ))

    # Forward A lookup
    a_result=$(dig_cmd A "$fqdn" 2>/dev/null | head -1)

    # Reverse PTR lookup
    ptr_result=$(dig_cmd -x "$ip" 2>/dev/null | head -1 | sed 's/\.$//')

    # Evaluate forward
    if [[ -z "$a_result" ]]; then
        a_label="${RED}NXDOMAIN${RESET}"
        a_ok=false
    elif [[ "$a_result" == "$ip" ]]; then
        a_label="${GREEN}OK${RESET} ($a_result)"
        a_ok=true
    else
        a_label="${YELLOW}MISMATCH${RESET} ($a_result)"
        a_ok=false
    fi

    # Evaluate reverse
    # strip trailing dot for comparison; do case-insensitive match
    fqdn_lower="${fqdn,,}"
    ptr_lower="${ptr_result,,}"

    if [[ -z "$ptr_result" ]]; then
        ptr_label="${RED}NXDOMAIN${RESET}"
        ptr_ok=false
    elif [[ "$ptr_lower" == "$fqdn_lower" || "$ptr_lower" == "${fqdn_lower}." ]]; then
        ptr_label="${GREEN}OK${RESET} ($ptr_result)"
        ptr_ok=true
    else
        ptr_label="${YELLOW}MISMATCH${RESET} ($ptr_result)"
        ptr_ok=false
    fi

    # Counters
    if $a_ok && $ptr_ok; then
        (( ok++ ))
    elif [[ -z "$a_result" || -z "$ptr_result" ]]; then
        (( fail++ ))
    else
        (( mismatch++ ))
    fi

    printf "%-45s %-18s %-55b %-55b\n" "$fqdn" "$ip" "$a_label" "$ptr_label"

done < "$INPUT"

# ── summary ────────────────────────────────────────────────────────────────────
printf '%s\n' "$(printf '%.0s─' {1..135})"
echo -e "\n${BOLD}Summary:${RESET}  Total: ${total}  |  ${GREEN}OK: ${ok}${RESET}  |  ${YELLOW}Mismatch: ${mismatch}${RESET}  |  ${RED}Failed: ${fail}${RESET}\n"
