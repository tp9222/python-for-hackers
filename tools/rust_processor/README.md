# RustScan Processor

Two scripts for automating RustScan execution across an IP list and aggregating open port results into a single summary file.

---

## Scripts

| Script | Purpose |
|---|---|
| `rust_commander.py` | Reads `ip_addresses.txt` and prints one `rustscan` command per IP (with output redirection) |
| `rust_processor.py` | Reads all per-IP `.txt` output files in the current directory and aggregates open ports into `rust_out.txt` |

---

## Requirements

- Python 3.8+ — stdlib only.
- [RustScan](https://github.com/RustScan/RustScan) installed and in PATH.

```bash
cargo install rustscan
# or
docker pull rustscan/rustscan
```

---

## Usage

### Step 1 — Generate and run commands

Add targets to `ip_addresses.txt` (one IP per line):

```
192.168.1.1
192.168.1.10
10.0.0.5
```

Generate commands:

```bash
python3 rust_commander.py
```

Output (copy-paste or pipe to bash):

```
rustscan -a 192.168.1.1 -- -Pn >> 192.168.1.1.txt
rustscan -a 192.168.1.10 -- -Pn >> 192.168.1.10.txt
rustscan -a 10.0.0.5 -- -Pn >> 10.0.0.5.txt
```

Or run automatically:

```bash
python3 rust_commander.py | bash
```

### Step 2 — Aggregate results

After all scans complete:

```bash
python3 rust_processor.py
```

Output (`rust_out.txt`):

```
192.168.1.1 --> 22, 80, 443
192.168.1.10 --> 21, 22, 3306, 8080
10.0.0.5 --> 22, 8443
```

---

## Notes

- `rust_processor.py` scans all `.txt` files in the current directory whose names match an IP pattern — ensure no unrelated `.txt` files are present.
- Duplicate ports are deduplicated per host.
- For the `rustautoscan.sh` alternative, see the bash script in the same directory.

---

## Disclaimer

For authorised penetration testing and security research only.
