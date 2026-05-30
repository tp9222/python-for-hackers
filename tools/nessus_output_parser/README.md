# Nessus Output Parser

Parses a Nessus CSV export and produces a clean, deduplicated summary grouping open ports by host and protocol. Useful for quickly extracting port lists from Nessus scan results for use in downstream tools.

---

## Requirements

```bash
pip install pandas
```

---

## Usage

Export your Nessus scan as CSV (Nessus UI → Report → Export → CSV).

Run the parser:

```bash
python3 nessus_output.py <path_to_nessus_export.csv>
```

---

## Output

Results are printed to stdout and saved to `output.txt` in the format:

```
<host> <PROTOCOL> <port1>, <port2>, <port3>
```

Example:

```
192.168.1.10 TCP 22, 80, 443, 8080
192.168.1.10 UDP 53, 161
192.168.1.20 TCP 21, 22, 3306
```

---

## Notes

- Duplicate host/protocol/port combinations are automatically removed.
- Protocol values are normalised to uppercase (tcp → TCP).
- Ports are sorted numerically within each group.
- The expected CSV columns are `Host`, `Protocol`, and `Port` — standard Nessus export format.

---

## Disclaimer

For authorised penetration testing and security research only.
