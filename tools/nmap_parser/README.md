# Nmap XML Output Parser

Three scripts for parsing nmap XML output into readable text reports, port lists, and ready-to-run nmap service scan commands.

---

## Scripts

| Script | Purpose |
|---|---|
| `nmap_output_parser.py` | Batch-parses all `.xml` files in the current directory → `nmap_output.txt` |
| `nmap_output_parser_oscp.py` | Same as above, plus generates `port_list.txt` and `nmap_commands.txt` for targeted service scans |
| `nmap_parser_singlefile.py` | Parses a single XML file specified interactively → `nmap.output` |

---

## Requirements

- Python 3.8+ — stdlib only, no external packages required.
- nmap XML output files (generated with `-oX` or `-oA`).

---

## Usage

### Batch parser — all XMLs in current directory

```bash
python3 nmap_output_parser.py
```

Output: `nmap_output.txt`

### OSCP-style batch parser

```bash
python3 nmap_output_parser_oscp.py
```

Output:
- `nmap_output.txt` — human-readable port/service summary
- `port_list.txt` — per-host TCP/UDP port lists
- `nmap_commands.txt` — ready-to-run targeted nmap commands

### Single file parser

```bash
python3 nmap_parser_singlefile.py
# Enter the Nmap XML file name: scan.xml
```

Output: `nmap.output`

---

## Output Format

### nmap_output.txt

```
192.168.1.10
hostname.local

   tcp / 22 / ssh / open
   tcp / 80 / http / open
   tcp / 443 / https / open
```

### port_list.txt (OSCP script only)

```
192.168.1.10 TCP: 22,80,443 UDP: 161
```

### nmap_commands.txt (OSCP script only)

```
nmap -oA 192.168.1.10_srv -sV -A -sC --script vuln -p 22,80,443 192.168.1.10
```

---

## Notes

- Input must be nmap XML format (`-oX` or `-oA`). Text format (`-oN`) is not supported.
- The OSCP script generates targeted service scans for each discovered TCP port — paste directly into a terminal.
- All three scripts handle multiple hosts per XML file.

---

## Disclaimer

For authorised penetration testing and security research only.
