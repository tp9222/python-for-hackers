# Filestack Security Auditor

A two-part penetration testing toolkit for identifying unrestricted file upload vulnerabilities in web applications that use Filestack as their file storage provider.

---

## The Vulnerability

Filestack is a third-party file upload and storage service. Its security model allows the **API key to be public** — security is enforced server-side through a signed **security policy** (a JSON object HMAC-SHA256 signed by the Filestack App Secret).

The policy supports a field called `allowed_file_types` which restricts what MIME types can be uploaded. When this field is **absent**, the policy accepts any file type regardless of what the front-end UI displays.

A common misconfiguration pattern:

```
Front-end (Flutter / React / Vue)
└── input[accept="image/jpeg,image/png"]   ← UI restriction only, zero enforcement

Filestack policy (server-generated)
└── {"expiry": 1234567890, "calls": ["pick","store","read","convert"]}
    ← NO allowed_file_types field → any file accepted by the API
```

An attacker with a valid authenticated session can bypass the UI entirely by calling the Filestack store API directly.

---

## Files

| File | Purpose |
|---|---|
| `filestack_grabber.js` | Paste in browser DevTools console — extracts credentials and prints the audit command |
| `filestack_policy_auditor.py` | Runs the audit — decodes the policy, checks for missing controls, optionally tests direct uploads |

---

## Requirements

- Python 3.8+ (no external dependencies — stdlib only)
- A browser with DevTools access on the target site
- An authenticated session on the target with file upload permissions (instructor / editor / admin role)

---

## Workflow

### Step 1 — Extract credentials from the browser

Open the target application in your browser. Log in with an account that has file upload access. Navigate to a page that contains a file upload feature (question editor, post creator, profile page, etc.).

Open DevTools → **Console** tab and paste the entire contents of `filestack_grabber.js`.

The script tries six extraction methods in order:

| # | Method | Covers |
|---|---|---|
| 1 | React 18 fiber (`__reactContainer$`) | React 18+ / Next.js apps |
| 2 | React <18 fiber (`__reactInternalInstance$`) | Older React apps |
| 3 | `window.store` / `window.__REDUX_STORE__` | Apps that expose the Redux store globally |
| 4 | Cookie parsing | Session stored in a cookie (JSON or raw suffix) |
| 5 | localStorage / sessionStorage | Persisted session state |
| 6 | XHR / fetch network hook | Falls back when nothing static is found — intercepts the next API call |

**If methods 1–5 succeed**, the command is printed immediately:

```
python filestack_policy_auditor.py --suffix "key=ABC123&policy=eyJ...&signature=abc..."
```

**If method 6 activates**, click any upload button on the page. The credentials appear automatically once the app calls its `/filestack/session` (or equivalent) endpoint.

---

### Step 2 — Run the auditor

```bash
# Copy-paste the command printed by the grabber
python filestack_policy_auditor.py --suffix "key=ABC123&policy=eyJ...&signature=abc..."

# Or run with no arguments for guided interactive mode
python filestack_policy_auditor.py
```

---

## Usage

### CLI flags

```
python filestack_policy_auditor.py [OPTIONS]

Credential input (one required):
  --suffix        Full suffix string: key=...&policy=...&signature=...
  --key           Filestack API key
  --policy        Base64-encoded policy
  --signature     HMAC-SHA256 signature (hex)
  --session-file  Path to JSON file saved from the /filestack/session API response

Options:
  --no-upload     Analyse policy only — no upload attempts (safe recon)
  --test-files    Comma-separated list of file types to test
                  Choices: txt, html, svg, js, php, xml, exe
                  Default: txt,html,svg,js
  --output-json   Write full results to a JSON file
  --verbose       Extra debug output
```

### Examples

```bash
# Policy analysis only — no network requests to Filestack
python filestack_policy_auditor.py --suffix "..." --no-upload

# Default test (txt, html, svg, js)
python filestack_policy_auditor.py --suffix "..."

# Full battery across all 7 file types
python filestack_policy_auditor.py --suffix "..." --test-files txt,html,svg,js,php,xml,exe

# Save results for report
python filestack_policy_auditor.py --suffix "..." --output-json results.json

# From a saved session JSON file
python filestack_policy_auditor.py --session-file filestack_session.json

# Interactive guided mode
python filestack_policy_auditor.py
```

---

## What the auditor checks

### Policy controls

| Field | Missing = | Severity |
|---|---|---|
| `allowed_file_types` | Any file type accepted — primary bypass vector | HIGH |
| `max_size` | No file size limit | MEDIUM |
| `expiry` | Policy never expires | HIGH |
| `path` | No S3 path restriction | LOW |
| `container` | No bucket restriction | LOW |

### Upload tests

When upload testing is enabled, the tool calls `POST www.filestackapi.com/api/store/S3` directly with each test file — bypassing any UI restriction. A `200 OK` response with `type: text/html` (or similar non-image type) confirms the bypass.

| Type | Filename | Risk if accepted |
|---|---|---|
| `txt` | pt_test.txt | Baseline — any non-image accepted indicates missing restriction |
| `html` | pt_test.html | Stored XSS / phishing page via trusted CDN |
| `svg` | pt_test.svg | SVG-based XSS (executes when served as image/svg+xml) |
| `js` | pt_test.js | Malicious JavaScript served from trusted CDN domain |
| `php` | pt_test.php | RCE if served by PHP-enabled host |
| `xml` | pt_test.xml | XXE payload testing |
| `exe` | pt_test.exe | Malware distribution vector |

---

## Output example

```
╔══════════════════════════════════════════════════════════════════════╗
║   Filestack Security Policy Auditor — Pentest Tool                   ║
╚══════════════════════════════════════════════════════════════════════╝

CREDENTIALS
──────────────────────────────────────────────────────────────────────
  [i] API Key   : AVBFBj0000  (public identifier — not a secret)
  [i] Policy    : eyJleHBpcnkiOjE3Nzg5OD...
  [i] Signature : 26f6727e45fd75533f...

POLICY CONTENT
──────────────────────────────────────────────────────────────────────
  [i] expiry: 1778988514
  [i] calls: ["pick","store","read","convert"]

SECURITY CONTROLS AUDIT
──────────────────────────────────────────────────────────────────────
  [✗] allowed_file_types          No file type whitelist — any file type can be uploaded
  [!] max_size                    No file size limit — arbitrary size uploads permitted
  [!] expiry                      EXPIRED — 2026-05-17 03:28:34 UTC
  [–] path                        No path restriction
  [–] container                   No container restriction
  [✓] calls                       Permitted: ['pick','store','read','convert']

UPLOAD BYPASS TEST
──────────────────────────────────────────────────────────────────────
  [i] Testing TXT   (pt_test.txt, text/plain) ...
  [✗] TXT    [200]  pt_test.txt  →  https://cdn.filestackcontent.com/abc123
  [i] Testing HTML  (pt_test.html, text/html) ...
  [✗] HTML   [200]  pt_test.html →  https://cdn.filestackcontent.com/def456  type=text/html

SUMMARY
──────────────────────────────────────────────────────────────────────
  [i] API Key        : AVBN26PPXRgSy6WDFBj00z  (public by design — not a finding alone)
  [i] Severity       : HIGH
  [i] CVSS           : 8.8 (AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:N)

  [✗] CRITICAL POLICY GAPS (1):
  [✗]   allowed_file_types — ABSENT → No file type whitelist enforced
```

---

## Remediation

The fix is a single field addition in the server-side policy generation code:

```python
policy = {
    "expiry": int(time.time()) + 900,          # 15-minute window
    "calls":  ["pick", "store", "read", "convert"],
    "allowed_file_types": ["image/jpeg", "image/png", "image/heic"],  # ADD THIS
    "max_size": 20971520                        # 20 MB — also recommended
}
```

With `allowed_file_types` set, the Filestack API rejects any upload that does not match — regardless of how the request is made.

---

## Important notes

**The Filestack API key is not a finding on its own.** Filestack's security model is designed for the API key to be client-facing (similar to a Stripe publishable key). The vulnerability is the missing `allowed_file_types` in the server-generated policy — not the key being visible.

**Upload tests write real files.** Each test file is under 1 KB but will appear in the target's Filestack account. Delete the handles from the Filestack dashboard after testing.

**Use only on authorised targets.** This tool makes real HTTP requests to Filestack's production API against the target's account. Ensure the target is within your penetration testing scope before running upload tests.

---

## Related

- [Filestack Security Documentation](https://www.filestack.com/docs/api/security/)
- [OWASP WSTG-UPLD-01 — Test File Upload Restrictions](https://owasp.org/www-project-web-security-testing-guide/)
- [CWE-434: Unrestricted Upload of File with Dangerous Type](https://cwe.mitre.org/data/definitions/434.html)
