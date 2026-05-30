# Nmap Output to IP List Provider

Extracts live IP addresses from nmap scan text output and writes them to a flat file for use in downstream tools.

---

## Requirements

- Python 3.8+ — stdlib only, no external packages required.

---

## Usage

Pipe nmap output to a file or use an existing nmap text output:

```bash
nmap -sn 192.168.1.0/24 -oN nmap_input.txt
```

Run the extractor:

```bash
python3 nmap_output_to_ip_list_provider.py
```

Output is written to `live_ips.txt` — one IP per line.

---

## Input Format

The script parses lines matching:

```
Nmap scan report for <IP>
```

Standard nmap text output (`-oN`) format. Does not require XML output.

---

## Example

Input (`nmap_input.txt`):

```
Nmap scan report for 192.168.1.1
Host is up (0.00050s latency).
Nmap scan report for 192.168.1.5
Host is up (0.00120s latency).
```

Output (`live_ips.txt`):

```
192.168.1.1
192.168.1.5
```

---

## Notes

- Only extracts IPs from lines containing `Nmap scan report for` — hostnames are not extracted.
- Compatible with output from ping sweep (`-sn`), service scans (`-sV`), and full scans.
- Feed `live_ips.txt` directly into PEEL, rustscan, or other tools that accept an IP list.

---

## Disclaimer

For authorised penetration testing and security research only.
