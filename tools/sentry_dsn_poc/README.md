# Sentry DSN Exposure PoC Tool

A desktop GUI tool for demonstrating unauthenticated Sentry event injection through exposed or publicly accessible Sentry DSNs.

This project is intended for:
- Security research
- Internal validation
- Bug bounty reporting
- Demonstrating DSN abuse scenarios safely in authorized environments

## Features

- Parse and validate Sentry DSNs
- Send custom Sentry events
- Generate reproducible `curl` commands
- Test different event levels and platforms
- Add tags, metadata, and extra fields
- View raw responses and HTTP status codes
- Demonstrate:
  - Event injection
  - Quota exhaustion risk
  - Misconfigured Sentry ingestion endpoints

## Screenshot

You can add screenshots here after running the application.

---

## Installation

### Clone the repository

```bash
git clone https://github.com/yourusername/sentry-dsn-poc.git
cd sentry-dsn-poc
```

### Install dependencies

```bash
pip install -r requirements.txt
```

---

## Requirements

- Python 3.9+
- tkinter
- requests

### Linux users

You may need to install tkinter manually:

```bash
sudo apt install python3-tk
```

---

## Usage

Run the application:

```bash
python sentry_dsn_poc.py
```

---

## Example Workflow

1. Paste a Sentry DSN
2. Configure payload fields
3. Send an event
4. Review HTTP responses
5. Validate whether the DSN accepts unauthenticated events

---

## Security & Legal Notice

Use this tool only against systems you own or are explicitly authorized to test.

This project is provided for:
- Defensive security testing
- Security research
- Responsible disclosure

Do not use this tool for unauthorized activity.

---

## License

MIT License
