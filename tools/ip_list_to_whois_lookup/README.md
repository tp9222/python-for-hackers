# IP List WHOIS Lookup

Two-script toolkit for bulk WHOIS lookups against a list of IP addresses, with a parser that extracts organization names into a CSV.

---

## Scripts

| Script | Purpose |
|---|---|
| `ip_list_to_whois_lookup.py` | Runs `whois` against each IP in `ip_list.txt`, saves raw output to `whois_output.txt` |
| `whois_output_parser.py` | Parses `whois_output.txt`, extracts IP + OrgName pairs into `whois_extracted.csv` |

---

## Requirements

- Python 3.8+
- `whois` CLI installed on the system

```bash
sudo apt install whois      # Debian/Ubuntu
brew install whois          # macOS
```

No external Python packages required — stdlib only.

---

## Usage

Add IP addresses to `ip_list.txt` (one per line):

```
1.1.1.1
8.8.8.8
192.0.2.1
```

Run WHOIS lookups:

```bash
python3 ip_list_to_whois_lookup.py
```

Parse results to CSV:

```bash
python3 whois_output_parser.py
```

---

## Output

`whois_output.txt` — raw WHOIS output for all IPs, separated by `===` dividers.

`whois_extracted.csv` — structured CSV:

```
IP Address,Organization Name
1.1.1.1,APNIC and Cloudflare DNS Resolver project
8.8.8.8,Google LLC
```

---

## Notes

- WHOIS lookups are sequential with a 10-second timeout per IP. Large lists will take time.
- The parser extracts the first `OrgName:` field per IP. Some WHOIS responses use `org-name` or `organisation` — extend the regex in `whois_output_parser.py` if needed.
- Rate limiting by WHOIS servers may cause failures for large batches. Add `time.sleep()` between requests if needed.

---

## Disclaimer

For authorised penetration testing and security research only.
