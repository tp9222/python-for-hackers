# Auto Web Surface PoC Tool

Automated web surface recon and security assessment tool. Takes one or more target domains, runs a structured set of checks, captures a homepage screenshot, and produces a self-contained HTML report per target.

---

## What It Checks

| Check | Details |
|---|---|
| Security Headers | CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| Cookie Flags | Secure flag presence per cookie |
| Host Header Reflection | Sends `Host: evil.example.com`, checks if reflected in response |
| Error Handling | Injects `'` into query string, looks for SQL/stack trace keywords |
| Sensitive File Exposure | Probes `/.git/config`, `/.env`, `/backup.zip`, `/database.sql`, `/admin/` |
| SSL/TLS | Runs `sslscan` if available |
| Open Ports | Runs `nmap -T4` |
| Homepage Screenshot | Captured with Playwright (Chromium headless) |

---

## Requirements

### Python packages

```bash
pip install -r requirements.txt
```

### Playwright browser

```bash
playwright install chromium
```

### System tools (optional but recommended)

```bash
sudo apt install nmap sslscan
```

---

## Usage

Single target:

```bash
python3 auto_web_poc.py -t example.com
```

Multiple targets (comma-separated):

```bash
python3 auto_web_poc.py -t example.com,api.example.com,staging.example.com
```

From a file (one target per line):

```bash
python3 auto_web_poc.py -f targets.txt
```

---

## Output Structure

```
output/
└── example.com_20260530_143055/
    ├── REPORT.html          ← self-contained HTML report
    ├── headers.txt
    ├── cookies.txt
    ├── host_header.txt
    ├── error_test.txt
    ├── sensitive_files.txt
    ├── sslscan.txt
    ├── nmap.txt
    └── screenshots/
        └── homepage.png
```

---

## Risk Scoring

Findings are tallied and scored:

| Score | Risk Level |
|---|---|
| ≥ 8 | High |
| ≥ 4 | Medium |
| < 4 | Low |

---

## Disclaimer

For authorised penetration testing and security research only.
