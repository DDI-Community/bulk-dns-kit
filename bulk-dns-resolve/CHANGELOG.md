# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] - 2026-03-18

### Added
- `--record-type` / `-r` — query any of `A`, `AAAA`, `CNAME`, `MX`, `NS`, `PTR`, `SRV`, `TXT` record types (previously hardcoded to `A` only)
- `--retries` — automatically retry timed-out queries up to N times before marking as `TIMEOUT` (default: `2`); retry count tracked in output as `attempts` field
- `--rate-limit` — token-bucket rate limiter caps queries per second across all threads to avoid overwhelming resolvers
- `--filter` — filter terminal output to specific statuses, e.g. `--filter FOUND,TIMEOUT`
- `--quiet` / `-q` — suppress per-query output and show only the final summary
- `--format` — choose between `csv` and `json` output formats; format also auto-detected from output file extension
- JSON output support via `write_json()`
- Colour-coded terminal output: green for `FOUND`, yellow for `TIMEOUT`, red for `ERROR`, dim for `NXDOMAIN`/`NOANSWER`; automatically disabled when stdout is not a TTY
- Progress bar via `tqdm` when installed; shown automatically unless `--show-all` is active; gracefully skipped if `tqdm` is not installed
- DNS server IP validation using Python `ipaddress` stdlib — rejects non-IP strings before any queries are sent
- `_extract_values()` — correctly parses record-type-specific fields (e.g. MX priority + exchange, SRV priority/weight/port/target, TXT byte strings)
- `RateLimiter` class — thread-safe token-bucket implementation
- `Colour` class — ANSI colour helpers with TTY-awareness
- `build_parser()` function — argument parser extracted from `main()` for cleaner separation
- Docstrings on all public functions and classes

### Changed
- Resolver instances are now **cached per thread** using `threading.local()` instead of being created fresh for every query — reduces object allocation overhead under high thread counts
- Result dict now includes `record_type` and `attempts` fields throughout the pipeline and in all output formats
- CSV output gains two new columns: `record_type` and `attempts`; column previously named `ip_addresses` renamed to `values` to reflect multi-type support
- Terminal header now displays `Record type` and `Rate limit` (when active) alongside existing fields
- Summary now prints `Total DNS queries sent (with retries)` in stats
- Minimum Python version raised from 3.8 to **3.10** (union type hint syntax)

### Fixed
- `split_fqdn()` edge case for bare names with no dot now explicitly documented and handled

---

## [0.1.0] - initial release

### Added
- Bulk A record resolution across a list of hostnames and domains
- Configurable DNS server via `-s` / `--server` (interactive prompt if omitted)
- Parallel resolution using `ThreadPoolExecutor` with configurable thread count (`--threads`, default: `20`)
- Configurable per-query timeout and resolver lifetime (`--timeout`, `--lifetime`)
- Per-query progress counter printed to terminal (`[N/total]`)
- `--show-all` flag to print all query attempts including failures
- Summary by hostname printed after all queries complete
- Status counts (`FOUND`, `NXDOMAIN`, `NOANSWER`, `TIMEOUT`, `ERROR`) printed as stats
- Optional CSV export via `--output` with columns: `hostname`, `domain`, `fqdn`, `status`, `ip_addresses`, `error`
- Input files support `#` comments and blank lines (both are skipped)
