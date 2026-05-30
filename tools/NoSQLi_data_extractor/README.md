# NoSQL Injection Data Extractor

Two blind NoSQL injection scripts for character-by-character extraction of usernames and passwords from MongoDB-backed login endpoints. Based on the regex injection technique demonstrated by IppSec.

Credit: [IppSec](https://www.youtube.com/watch?v=NO_lsfhQK_s&t=747s)

---

## Scripts

| Script | Purpose |
|---|---|
| `username_extractor.py` | Extracts usernames via `username[$regex]` blind injection |
| `password.py` | Extracts passwords for a known username via `password[$regex]` blind injection |

---

## How It Works

Both scripts exploit MongoDB's `$regex` operator in login form parameters. By injecting `^<partial_value>` and checking whether the response differs (e.g., redirect vs. 200), characters are enumerated one at a time.

**Vulnerable parameter example:**

```
POST /login
username[$regex]=^a&password[$ne]=x
```

If the status code is not 200, a user starting with `a` exists.

---

## Requirements

```bash
pip install requests
```

---

## Configuration

Before running, edit these values in each script:

```python
r = requests.post('http://TARGET_URL/', data=data, allow_redirects=False)
```

For `password.py`, also set the known username:

```python
"username": "admin"
```

For `username_extractor.py`, set `secret` to the last confirmed prefix if resuming mid-extraction:

```python
secret = ""  # e.g. "admi" to resume from there
```

---

## Usage

Extract usernames:

```bash
python3 username_extractor.py
```

Extract password for a known user:

```bash
python3 password.py
```

Output is printed character by character in place on a single line. The complete extracted value is printed when extraction finishes.

---

## Notes

- `username_extractor.py` iterates `a-z` (ASCII 97–122). Extend `range(32, 126)` for full printable character set.
- `password.py` iterates full printable ASCII (32–125) and escapes regex metacharacters (`. * ? ^ +`).
- A response status other than 200 is treated as a successful injection match. Adjust the condition if the target uses different status codes.
- Both scripts stop when the full `^value$` regex matches — indicating the complete string has been found.

---

## Disclaimer

For authorised penetration testing and security research only.
