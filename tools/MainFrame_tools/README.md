# Mainframe Penetration Testing Tools

TN3270 mainframe interaction and attack tooling for authorized penetration testing of IBM mainframe environments.

---

## Scripts

| Script | Purpose |
|---|---|
| `Interceptor.py` | Connects to a TN3270 endpoint, attempts brute-force of a 4-digit supervisor code, and reveals hidden fields by modifying field attribute bytes |

---

## Requirements

```bash
pip install telnetlib3
```

---

## Usage

Edit `Interceptor.py` to set the target:

```python
MAINFRAME_IP   = "127.0.0.1"   # Target IP
MAINFRAME_PORT = 23             # TN3270 port (default 23)
```

Run:

```bash
python3 Interceptor.py
```

---

## What It Does

1. **Connect** — establishes a TN3270 session via Telnet.
2. **Brute-force supervisor code** — iterates `0000–9999`, sends each as input, checks the response for an `Access Granted` keyword. Adjust the success keyword to match the target application.
3. **Reveal hidden fields** — scans the raw TN3270 screen buffer and replaces hidden field attribute bytes (`0x1D`) with visible ones (`0x1F`).

---

## Notes

- TN3270 uses a field-based screen model. Hidden fields are not transmitted to the client in standard sessions but may be present in the raw data stream.
- The brute-force word list covers all 4-digit numeric codes (10,000 entries). For alpha-numeric codes, extend the `wordlist` accordingly.
- Adjust the `Access Granted` check string to match the actual success response of the target application.
- The `0.1s` sleep between attempts avoids flooding — increase for slower mainframes or environments with rate limiting.

---

## Disclaimer

For authorised penetration testing and security research only. Mainframe systems are often critical infrastructure — obtain explicit written permission before testing.
