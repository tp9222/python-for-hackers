# Google Dork Scanner

Rate-limited Google dorking tool with adaptive backoff, auto-resume, User-Agent rotation, and structured output (TXT + CSV). Prepends `site:<target>` to each dork and saves all results for offline analysis.

---

## What It Does

- Reads dorks from `dorks.txt` (one per line, `#` for comments)
- Prepends `site:<target>` to each dork automatically
- Searches Google via `requests` + `BeautifulSoup` HTML parsing
- Adaptive rate-limit handling — exponential backoff on 429/CAPTCHA, gradual recovery
- Rotates User-Agent strings across 5 browser profiles
- Saves progress to `.dork_scan_state.json` — resume interrupted scans with `--resume`
- Outputs results as timestamped `.txt` and `.csv`

---

## Requirements

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
python3 google_dork_scanner.py -t example.com -d dorks.txt
```

Interactive wait time prompt if `--min-wait`/`--max-wait` not set:

```
Enter MINIMUM wait time (seconds) [default: 5]:
Enter MAXIMUM wait time (seconds) [default: 15]:
```

Resume an interrupted scan:

```bash
python3 google_dork_scanner.py -t example.com -d dorks.txt --resume
```

Custom result count and output file:

```bash
python3 google_dork_scanner.py -t example.com -d dorks.txt -n 20 -o results_example.txt
```

---

## CLI Flags

| Flag | Default | Description |
|---|---|---|
| `-t / --target` | required | Target domain (e.g. `example.com`) |
| `-d / --dorks` | required | Path to dorks file |
| `-o / --output` | auto-generated | Output `.txt` file path |
| `--min-wait` | interactive | Minimum seconds between queries |
| `--max-wait` | interactive | Maximum seconds between queries |
| `-n / --num` | `10` | Results per dork |
| `--timeout` | `15` | HTTP timeout in seconds |
| `--resume` | off | Resume from last saved state |
| `--no-color` | off | Disable ANSI colour output |

---

## Dorks File Format

```
# Directory listing
intitle:"index of" "parent directory"

# Exposed config
filetype:env "DB_PASSWORD"

# Login pages
inurl:admin intitle:login
```

Blank lines and lines starting with `#` are skipped. See included `dorks.txt` for a ready-to-use starter set.

---

## Output

`results_<target>_<timestamp>.txt` — structured text with dork, timestamp, titles, URLs, and snippets.

`results_<target>_<timestamp>.csv` — same data in CSV with columns: `Timestamp, Target, Dork, Title, URL, Snippet`.

---

## Notes

- Excessive automated Google queries may trigger CAPTCHAs or temporary IP blocks. Use conservative wait times (10–30s minimum) for production targets.
- This tool does not bypass CAPTCHA — if blocked, wait and retry or use a different IP.
- Google's Terms of Service prohibit automated scraping. Use only on authorised targets and within applicable legal frameworks.

---

## Disclaimer

For authorised security research and penetration testing only.
