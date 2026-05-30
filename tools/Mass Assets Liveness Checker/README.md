# Mass Assets Liveness Checker

Flask-based web GUI for bulk URL/host liveness checking with custom port support, User-Agent spoofing, screenshot capture, and Excel report export.

---

## What It Does

- Accepts a list of hosts via paste or file upload (`.txt` / `.xlsx`)
- Checks HTTP/HTTPS liveness across configurable port combinations using concurrent threads
- Spoofs User-Agent and browser headers (Chrome, Firefox, Safari, Edge, Android, iOS — 15 profiles)
- Optionally captures screenshots of live URLs via Playwright, Selenium, gowitness, cutycapt, or headless Chrome
- Streams real-time scan progress and console output via SSE
- Exports results to a timestamped Excel workbook (colour-coded by status)
- Gallery view for captured screenshots

---

## Requirements

```bash
pip install -r requirements.txt
```

For screenshot support (install at least one):

```bash
pip install playwright && playwright install chromium
pip install selenium   # + chromedriver in PATH
sudo apt install cutycapt
sudo apt install wkhtmltopdf
go install github.com/sensepost/gowitness@latest
```

---

## Usage

```bash
python3 mass_assets_liveness_checker.py
```

Open browser at `http://127.0.0.1:5001`

1. Paste hosts or upload a `.txt`/`.xlsx` file (one host per line, no protocol)
2. Configure ports (default: `80,443,8080,8443`)
3. Select a User-Agent profile
4. Toggle screenshots on/off
5. Click **Start Scan**
6. Download Excel report or view screenshot gallery when complete

---

## Port Presets

| Preset | Ports |
|---|---|
| Web | `80,443` |
| Extended | `80,443,8080,8443,3000,5000,9090` |
| Full | 21 common ports including FTP, SSH, SMTP, RDP, databases |

---

## User-Agent Profiles

15 profiles covering Chrome/Firefox/Safari/Edge on Windows/macOS/Linux, Chrome/Firefox/Samsung on Android, and Safari/Chrome on iOS. Plus a random-rotate mode that picks a different profile per request.

---

## Output

- `reports/url_check_<jobid>_<timestamp>.xlsx` — colour-coded Excel report
- `reports/screenshots_<jobid>/` — PNG screenshots of live URLs (if enabled)

---

## Status Codes

| Status | Meaning |
|---|---|
| ACTIVE | HTTP response received |
| INACTIVE | Connection refused |
| TIMEOUT | No response within timeout |
| SSL_ERROR | TLS handshake failure |

---

## Disclaimer

For authorised penetration testing and security research only.
