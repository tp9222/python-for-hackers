# Echo Port Scanner

Lightweight port scanners implemented in pure Bash (using `/dev/tcp`) and Python (`socket`), with no dependency on nmap or other external scan tools. Outputs results as XML and plain text.

---

## Scripts

| Script | Purpose |
|---|---|
| `echo_bash_port_scanner.sh` | Bash `/dev/tcp` port scanner — basic version |
| `echo_bash_portscanner_v2.sh` | Bash scanner with progress bar and fixed scan type validation |
| `echo_python_scanner.py` | Python `socket` scanner — cross-platform |

---

## Requirements

### Bash scripts
- Bash 4+ (Linux/macOS)
- No external tools required — uses `/dev/tcp` pseudo-device

### Python script
- Python 3.8+ — stdlib only, no external packages

---

## Usage

### Bash scanners

```bash
chmod +x echo_bash_port_scanner.sh
./echo_bash_port_scanner.sh
# Enter target IP: 192.168.1.10
# Select scan type (1 for well-known ports, 2 for top 1000 ports, 3 for all ports): 1
```

Output saved to `scan_results/port_scan_<timestamp>.xml` and `scan_results/port_scan_<timestamp>.txt`.

### Python scanner

```bash
python3 echo_python_scanner.py
# Enter target IP: 192.168.1.10
# Select scan type (1 for well-known ports, 2 for top 1000 ports, 3 for all ports): 2
```

Output saved to `port_scan_<scantype>.xml` and `port_scan_<scantype>.txt`.

---

## Scan Modes

| Mode | Coverage |
|---|---|
| 1 | Well-known ports (20–1024) |
| 2 | Top ~1000 ports (nmap-style list) |
| 3 | All ports (1–65535) |

---

## Output Format

### XML

```xml
<port_scan>
    <port>
        <number>22</number>
        <status>open</status>
    </port>
    <port>
        <number>80</number>
        <status>open</status>
    </port>
</port_scan>
```

### Text

```
Port 22 is open
Port 80 is open
```

---

## Notes

- The Bash scanner is significantly slower than nmap for large port ranges due to sequential `/dev/tcp` probing. Use mode 1 or 2 for speed.
- The Python scanner uses a 1-second socket timeout per port. Adjust `sock.settimeout(1)` for slower networks.
- `/dev/tcp` is a Bash built-in and is not available in `sh` or `dash`.

---

## Disclaimer

For authorised penetration testing and security research only.
