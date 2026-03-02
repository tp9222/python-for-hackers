# auto_web_poc.py

import sys
import shutil
import base64
import requests
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.progress import Progress

console = Console()
TIMEOUT = 8


# =====================================================
# Utility
# =====================================================

def create_output_folder(target):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path("output") / f"{target}_{timestamp}"
    screenshots = base / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    return base, screenshots


def save_file(path, filename, content):
    (path / filename).write_text(str(content), encoding="utf-8")


def run_cmd(cmd, timeout=300):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout
    except Exception as e:
        return f"Command error: {e}"


def get_binary(name):
    return shutil.which(name)


def screenshot_content(content, output_path, is_url=False):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            if is_url:
                page.goto(content, timeout=20000, wait_until="domcontentloaded")
            else:
                page.set_content(content)

            page.screenshot(path=str(output_path), full_page=True)
            browser.close()
    except Exception as e:
        console.print(f"[red]Screenshot failed: {e}[/red]")


def image_to_base64(path):
    try:
        return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()
    except:
        return ""


# =====================================================
# Checks
# =====================================================

def run_httpx(target):
    httpx = get_binary("httpx")
    if not httpx:
        return "httpx not found"
    return run_cmd([httpx, "-u", target, "-status-code", "-title",
                    "-tech-detect", "-server", "-web-server", "-ip"])


def fetch(url):
    try:
        return requests.get(url, timeout=TIMEOUT)
    except:
        return None


def analyze_headers(response):
    if not response:
        return "No response"

    required = [
        "Content-Security-Policy",
        "Strict-Transport-Security",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy"
    ]

    result = []
    for h in required:
        if h in response.headers:
            result.append(f"[OK] {h}")
        else:
            result.append(f"[MISSING] {h}")

    return "\n".join(result)


def analyze_cookies(response):
    if not response or not response.cookies:
        return "No cookies set"

    lines = []
    for c in response.cookies:
        secure = "Secure" if c.secure else "Secure missing"
        lines.append(f"{c.name}: {secure}")

    return "\n".join(lines)


def check_host_header(base_url):
    try:
        headers = {"Host": "evil.example.com"}
        r = requests.get(base_url, headers=headers, timeout=TIMEOUT)
        if "evil.example.com" in r.text:
            return "Host header reflection detected"
        return "No host header reflection"
    except:
        return "Host header test failed"


def check_error_handling(base_url):
    try:
        r = requests.get(f"{base_url}/?test='", timeout=TIMEOUT)
        indicators = ["sql syntax", "exception", "traceback", "stack trace"]
        for i in indicators:
            if i in r.text.lower():
                return "Verbose error disclosure detected"
        return "No obvious error-based issue"
    except:
        return "Error test failed"


def check_sensitive_files(base_url):
    paths = ["/.git/config", "/.env", "/backup.zip",
             "/database.sql", "/admin/"]

    exposed = []
    for p in paths:
        try:
            r = requests.get(urljoin(base_url, p), timeout=5)
            if r.status_code == 200:
                exposed.append(p)
        except:
            pass

    return "\n".join(exposed) if exposed else "No common sensitive files exposed"


def run_sslscan(target):
    sslscan = get_binary("sslscan")
    if not sslscan:
        return "sslscan not found"
    return run_cmd([sslscan, "--no-colour", target])


def run_nmap(target):
    nmap = get_binary("nmap")
    if not nmap:
        return "nmap not found"

    result = run_cmd([nmap, "-T4", target], timeout=180)
    if "Host seems down" in result:
        result = run_cmd([nmap, "-T4", "-Pn", target], timeout=180)
    return result


# =====================================================
# Risk
# =====================================================

def calculate_risk(findings):
    score = len(findings) * 2
    if score >= 8:
        return "High", score
    elif score >= 4:
        return "Medium", score
    return "Low", score


# =====================================================
# Scan
# =====================================================

def run_scan(target):

    console.print(f"[bold green]Starting Review for {target}[/bold green]")

    base, screenshots = create_output_folder(target)
    base_url = f"https://{target}"

    findings = []

    with Progress() as progress:
        task = progress.add_task("[cyan]Scanning...", total=8)

        response = fetch(base_url)
        progress.update(task, advance=1)

        headers = analyze_headers(response)
        save_file(base, "headers.txt", headers)
        if "[MISSING]" in headers:
            findings.append("Missing Security Headers")
        progress.update(task, advance=1)

        cookies = analyze_cookies(response)
        save_file(base, "cookies.txt", cookies)
        progress.update(task, advance=1)

        host = check_host_header(base_url)
        save_file(base, "host_header.txt", host)
        if "reflection" in host.lower():
            findings.append("Host Header Reflection")
        progress.update(task, advance=1)

        error = check_error_handling(base_url)
        save_file(base, "error_test.txt", error)
        if "verbose" in error.lower():
            findings.append("Verbose Error Disclosure")
        progress.update(task, advance=1)

        sensitive = check_sensitive_files(base_url)
        save_file(base, "sensitive_files.txt", sensitive)
        if "No common" not in sensitive:
            findings.append("Sensitive File Exposure")
        progress.update(task, advance=1)

        sslscan = run_sslscan(target)
        save_file(base, "sslscan.txt", sslscan)
        progress.update(task, advance=1)

        nmap = run_nmap(target)
        save_file(base, "nmap.txt", nmap)
        progress.update(task, advance=1)

        screenshot_content(base_url, screenshots / "homepage.png", True)
        progress.update(task, advance=1)

    risk_level, risk_score = calculate_risk(findings)

    # Clean Nmap
    nmap_clean = "\n".join([l for l in nmap.splitlines()
                            if "/tcp" in l or "PORT" in l])

    homepage_img = image_to_base64(screenshots / "homepage.png")

    # Professional HTML
    html = f"""
    <html>
    <head>
    <style>
    body {{ font-family: Arial; background:#f4f4f4; padding:30px }}
    .card {{ background:white; padding:20px; margin-bottom:25px;
             border-radius:8px; box-shadow:0 2px 6px rgba(0,0,0,0.1) }}
    pre {{ background:#111; color:#00ff00; padding:15px; overflow-x:auto }}
    table {{ width:100%; border-collapse:collapse }}
    th, td {{ padding:10px; border-bottom:1px solid #ddd }}
    th {{ background:#f2f2f2 }}
    </style>
    </head>
    <body>

    <h1>Web Surface Security Assessment</h1>
    <h2>Target: {target}</h2>
    <h3>Risk Level: {risk_level} (Score: {risk_score})</h3>

    <div class="card">
    <h3>Executive Summary</h3>
    <p>Automated security review of exposed web surface and services.</p>
    </div>

    <div class="card">
    <h3>Findings Overview</h3>
    <table>
    <tr><th>Finding</th></tr>
    {"".join(f"<tr><td>{f}</td></tr>" for f in findings) or "<tr><td>No major issues identified</td></tr>"}
    </table>
    </div>

    <div class="card"><h3>Homepage Screenshot</h3>
    <img src="{homepage_img}" width="100%"></div>

    <div class="card"><h3>Security Headers</h3><pre>{headers}</pre></div>
    <div class="card"><h3>Cookies</h3><pre>{cookies}</pre></div>
    <div class="card"><h3>Host Header Test</h3><pre>{host}</pre></div>
    <div class="card"><h3>Error Handling</h3><pre>{error}</pre></div>
    <div class="card"><h3>Sensitive Files</h3><pre>{sensitive}</pre></div>
    <div class="card"><h3>SSL/TLS</h3><pre>{sslscan}</pre></div>
    <div class="card"><h3>Open Ports (Nmap)</h3><pre>{nmap_clean}</pre></div>

    </body>
    </html>
    """

    save_file(base, "REPORT.html", html)

    console.print(f"[bold yellow]Risk Level: {risk_level} ({risk_score})[/bold yellow]")
    console.print(f"[bold green]Completed: {base}[/bold green]")


# =====================================================
# CLI
# =====================================================

def main():
    parser = argparse.ArgumentParser(
        description="Auto Web Surface Recon Tool",
        epilog="""
Examples:
  python3 auto_web_poc.py -t example.com
  python3 auto_web_poc.py -t example.com,nmap.org
  python3 auto_web_poc.py -f targets.txt
""",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument("-t", "--target",
                        help="Single or comma-separated targets")
    parser.add_argument("-f", "--file",
                        help="File containing targets (one per line)")

    args = parser.parse_args()

    if not args.target and not args.file:
        parser.print_help()
        sys.exit(0)

    targets = []

    if args.target:
        targets.extend([t.strip() for t in args.target.split(",") if t.strip()])

    if args.file:
        lines = Path(args.file).read_text().splitlines()
        targets.extend([l.strip() for l in lines if l.strip()])

    console.print(f"[bold cyan]Total Targets: {len(targets)}[/bold cyan]")

    for t in targets:
        run_scan(t)


if __name__ == "__main__":
    main()
