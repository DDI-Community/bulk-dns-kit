#!/usr/bin/env bash
# =============================================================================
# check_cnames.sh — Validate CNAMEs resolve to at least one A record / IP
# =============================================================================
# Usage:
#   chmod +x check_cnames.sh
#   ./check_cnames.sh cnames.txt
#   ./check_cnames.sh cnames.txt --dns 8.8.8.8 --verbose
#   ./check_cnames.sh cnames.txt --dns 1.1.1.1 --output results.csv
#
# Input file format (one CNAME per line, # lines are ignored):
#   www.example.com
#   api.example.com
#   # this is a comment
#
# Output CSV columns:
#   cname, status, resolved_ip, checked_at
# =============================================================================

# NOTE: intentionally NOT using set -e here — a failed dig for one entry
# must never abort the entire run. We handle errors per-row instead.
set -uo pipefail

# ── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

# ── args ──────────────────────────────────────────────────────────────────────
INPUT_FILE="${1:-}"
VERBOSE=false
DNS_SERVER=""
OUTPUT_FILE=""

shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --verbose) VERBOSE=true ;;
    --dns)
      DNS_SERVER="${2:-}"
      if [[ -z "$DNS_SERVER" ]]; then
        echo -e "${RED}Error:${RESET} --dns requires an argument (e.g. --dns 8.8.8.8)"
        exit 1
      fi
      shift
      ;;
    --output)
      OUTPUT_FILE="${2:-}"
      if [[ -z "$OUTPUT_FILE" ]]; then
        echo -e "${RED}Error:${RESET} --output requires a filename (e.g. --output results.csv)"
        exit 1
      fi
      shift
      ;;
    *) echo -e "${YELLOW}Warning:${RESET} Unknown argument: $1" ;;
  esac
  shift
done

if [[ -z "$INPUT_FILE" ]]; then
  echo -e "${BOLD}Usage:${RESET} $0 <cnames_file> [--dns <server>] [--output <file.csv>] [--verbose]"
  echo -e "  Examples:"
  echo -e "    $0 cnames.txt"
  echo -e "    $0 cnames.txt --dns 8.8.8.8 --verbose"
  echo -e "    $0 cnames.txt --dns 1.1.1.1 --output results.csv"
  exit 1
fi

if [[ ! -f "$INPUT_FILE" ]]; then
  echo -e "${RED}Error:${RESET} File not found: $INPUT_FILE"
  exit 1
fi

# ── dependency check ──────────────────────────────────────────────────────────
if ! command -v dig &>/dev/null; then
  echo -e "${RED}Error:${RESET} 'dig' is required but not installed."
  echo "  Install with: sudo apt install dnsutils  (Debian/Ubuntu)"
  echo "                brew install bind           (macOS)"
  exit 1
fi

# ── output files ──────────────────────────────────────────────────────────────
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BROKEN_FILE="broken_cnames_${TIMESTAMP}.txt"
OK_FILE="ok_cnames_${TIMESTAMP}.txt"

# Write CSV header if --output was requested
if [[ -n "$OUTPUT_FILE" ]]; then
  echo "cname,status,resolved_ip,checked_at" > "$OUTPUT_FILE"
fi

ok_count=0
broken_count=0
skip_count=0
error_count=0

echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}${CYAN}  CNAME Resolution Checker${RESET}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════${RESET}"
echo -e "  Input  : ${INPUT_FILE}"
echo -e "  DNS    : ${DNS_SERVER:-system default}"
echo -e "  Output : ${OUTPUT_FILE:-none (use --output <file.csv> to enable)}"
echo -e "  Verbose: ${VERBOSE}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════${RESET}\n"

# ── main loop ─────────────────────────────────────────────────────────────────
while IFS= read -r line || [[ -n "$line" ]]; do
  # strip whitespace
  cname=$(echo "$line" | xargs 2>/dev/null || true)

  # skip empty lines and comments
  if [[ -z "$cname" || "$cname" == \#* ]]; then
    ((skip_count++)) || true
    continue
  fi

  ROW_TIME=$(date +%Y-%m-%dT%H:%M:%S)

  # follow the full chain — run in subshell so any error is captured, never fatal
  DIG_SERVER=""
  [[ -n "$DNS_SERVER" ]] && DIG_SERVER="@${DNS_SERVER}"
  resolved=$(dig +short +tries=2 +time=5 $DIG_SERVER "$cname" 2>/dev/null | tail -n 1) || true

  # ── classify result ──────────────────────────────────────────────────────
  if [[ "$resolved" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || [[ "$resolved" =~ : ]]; then
    # resolves to an IP (IPv4 or IPv6) → OK
    echo "$cname" >> "$OK_FILE"
    [[ -n "$OUTPUT_FILE" ]] && echo "${cname},OK,${resolved},${ROW_TIME}" >> "$OUTPUT_FILE"
    ((ok_count++)) || true
    $VERBOSE && echo -e "  ${GREEN}OK${RESET}      ${cname}  →  ${resolved}"

  elif [[ -z "$resolved" ]]; then
    # dig returned nothing at all — timeout, NXDOMAIN, or dig itself failed
    echo "$cname" >> "$BROKEN_FILE"
    [[ -n "$OUTPUT_FILE" ]] && echo "${cname},ERROR,,${ROW_TIME}" >> "$OUTPUT_FILE"
    ((error_count++)) || true
    echo -e "  ${YELLOW}ERROR${RESET}   ${cname}  →  ${YELLOW}<no response / timeout>${RESET}"

  else
    # got an answer but it's not an IP (dangling CNAME chain, SERVFAIL text, etc.)
    echo "$cname" >> "$BROKEN_FILE"
    [[ -n "$OUTPUT_FILE" ]] && echo "${cname},BROKEN,${resolved},${ROW_TIME}" >> "$OUTPUT_FILE"
    ((broken_count++)) || true
    echo -e "  ${RED}BROKEN${RESET}  ${cname}  →  ${YELLOW}${resolved}${RESET}"
  fi

done < "$INPUT_FILE"

# ── summary ───────────────────────────────────────────────────────────────────
total=$((ok_count + broken_count + error_count))
echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  Summary${RESET}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════${RESET}"
printf "  %-12s %s\n"                          "Total:"   "$total"
printf "  %-12s ${GREEN}%s${RESET}\n"          "OK:"      "$ok_count"
printf "  %-12s ${RED}%s${RESET}\n"            "Broken:"  "$broken_count"
printf "  %-12s ${YELLOW}%s${RESET}\n"         "Error:"   "$error_count"
printf "  %-12s %s\n"                          "Skipped:" "$skip_count"
echo ""
[[ $((broken_count + error_count)) -gt 0 ]] && \
  echo -e "  Broken/Error list → ${BOLD}${BROKEN_FILE}${RESET}"
[[ $ok_count -gt 0 ]] && \
  echo -e "  OK list           → ${BOLD}${OK_FILE}${RESET}"
[[ -n "$OUTPUT_FILE" ]] && \
  echo -e "  Full report       → ${BOLD}${OUTPUT_FILE}${RESET}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════${RESET}\n"
