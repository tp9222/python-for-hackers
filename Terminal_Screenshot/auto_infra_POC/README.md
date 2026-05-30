# Auto Infrastructure PoC Scanner

Automated infrastructure penetration testing tool that runs nmap, sslscan, and nuclei against a target list, captures terminal output as PNG screenshots, and generates per-target and master HTML reports.

---

## What It Does

- Reads targets from `ip.txt` (one IP or hostname per line)
- Runs nmap port scan (fast top-1000 or full `-p-`)
- Runs sslscan against port 443 if detected open
- Runs nuclei against HTTP/HTTPS services
- Converts each scan's terminal output to a PNG screenshot via `wkhtmltoimage`
- Generates a per-target `report.html` and a master `master_report.html`
- All results are saved under `scan_results/PT_<timestamp>/`

---

## Known Issues

- TLS scan results contain extra characters in screenshots
- HeartBleed is always reported as vulnerable (false positive — verify manually)

---

## Requirements

### Python packages

```bash
pip install -r requirements.txt
```

### System tools (must be in PATH)

```bash
sudo apt install nmap sslscan golang wkhtmltopdf
go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
nuclei -update-templates
```

Run `setup.py` to install all dependencies automatically:

```bash
python3 setup.py
```

---

## Usage

Add targets to `ip.txt`:

```
192.168.1.1
192.168.1.10
internal.example.com
```

Run the scanner:

```bash
python3 unified_pt.py
```

Select scan mode when prompted:

```
1 → Fast Scan   (top 1000 ports, -sC -sV)
2 → Full Scan   (all 65535 ports, -sC -sV)
```

---

## Output Structure

```
scan_results/
└── PT_20260530_143055/
    ├── master_report.html
    ├── 192.168.1.1/
    │   ├── nmap.txt
    │   ├── sslscan.txt
    │   ├── nuclei.txt
    │   ├── report.html
    │   └── screenshots/
    │       ├── nmap.png
    │       ├── sslscan.png
    │       └── nuclei.png
    └── 192.168.1.10/
        └── ...
```

---

## Disclaimer

For authorised penetration testing and security research only.
