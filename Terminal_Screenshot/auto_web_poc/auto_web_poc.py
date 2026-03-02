import sys
import shutil
import base64
import requests
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.progress import Progress

console = Console()
TIMEOUT = 8


# ==============================
# Utility
# ==============================

def create_output_folder(target):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path("output") / f"{target}_{timestamp}"
    screenshots = base / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    return base, screenshots


def save_file(path, filename, content):
    with open(path / filename, "w", encoding="utf-8") as f:
        f.write(str(content))


def run_cmd(cmd, timeout=300):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout
    except Exception as e:
        return str(e)


def screenshot_content(content, output_path, is_url=False):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            if is_url:
                page.goto(content, timeout=15000, wait_until="commit")
            else:
                page.set_content(content)

            page.screenshot(path=str(output_path), full_page=True)
            browser.close()
    except Exception as e:
        console.print(f"[red]Screenshot failed: {e}[/red]")


def image_to_base64(image_path):
    try:
        with open(image_path, "rb") as img:
            return "data:image/png;base64," + base64.b64encode(img.read()).decode()
    except:
        return ""


def get_binary(name):
    return shutil.which(name)


# ==============================
# Core Checks
# ==============================

def run_httpx(target):
    httpx = get_binary("httpx")
    if not httpx:
        return "httpx not found"

    return run_cmd([
        httpx, "-u", target,
        "-status-code", "-title",
        "-tech-detect", "-server",
        "-web-server", "-ip"
    ])


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

    report = ""
    for h in required:
        if h in response.headers:
            report += f"[OK] {h} present\n"
        else:
            report += f"[MISSING] {h}\n"

    return report


def analyze_cookies(response):
    if not response or not response.cookies:
        return "No cookies set"

    report = ""
    for c in response.cookies:
        report += f"Cookie: {c.name}\n"
        report += "  Secure\n" if c.secure else "  Secure missing\n"
    return report


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


def check_robots(base_url):
    r = fetch(urljoin(base_url, "/robots.txt"))
    if not r or r.status_code != 200:
        return "robots.txt not accessible"
    return r.text


# ==============================
# Exposure Checks
# ==============================

def check_sensitive_files(base_url):
    paths = [
        "/.git/config",
        "/.env",
        "/.DS_Store",
        "/backup.zip",
        "/backup.tar.gz",
        "/config.php.bak",
        "/database.sql",
        "/db.sql",
        "/admin/"
    ]

    findings = []
    for path in paths:
        try:
            r = requests.get(urljoin(base_url, path), timeout=5)
            if r.status_code == 200:
                findings.append(path)
        except:
            pass

    return "\n".join(findings) if findings else "No common sensitive files exposed"


def check_graphql(base_url):
    endpoints = ["/graphql", "/api/graphql"]

    for ep in endpoints:
        try:
            r = requests.post(
                urljoin(base_url, ep),
                json={"query": "{ __typename }"},
                timeout=5
            )
            if "data" in r.text:
                return f"GraphQL endpoint detected at {ep}"
        except:
            pass

    return "No GraphQL endpoint detected"


def check_swagger(base_url):
    paths = [
        "/swagger",
        "/swagger-ui",
        "/v2/api-docs",
        "/openapi.json"
    ]

    for path in paths:
        try:
            r = requests.get(urljoin(base_url, path), timeout=5)
            if r.status_code == 200:
                return f"Swagger exposed at {path}"
        except:
            pass

    return "No Swagger exposure detected"


def check_directory_listing(base_url):
    r = fetch(base_url)
    if r and "Index of /" in r.text:
        return "Directory listing enabled"
    return "No directory listing detected"


# ==============================
# Network
# ==============================

def run_sslscan(target):
    sslscan = get_binary("sslscan")
    if not sslscan:
        return "sslscan not found"
    return run_cmd([sslscan, "--no-colour", target])


def run_nmap(target):
    nmap = get_binary("nmap")
    if not nmap:
        return "nmap not found"
    return run_cmd([nmap, "-T4", "-Pn", target])


# ==============================
# Risk Engine
# ==============================

def calculate_risk(findings):
    score = sum(f["score"] for f in findings)

    if score >= 8:
        level = "High"
    elif score >= 4:
        level = "Medium"
    else:
        level = "Low"

    return level, score


# ==============================
# Main
# ==============================

def run_all(target):

    console.print(f"[bold green]Starting Review for {target}[/bold green]")

    base, screenshots = create_output_folder(target)
    base_url = f"https://{target}"
    findings = []

    with Progress() as progress:
        task = progress.add_task("[cyan]Scanning...", total=14)

        httpx_output = run_httpx(target)
        save_file(base, "httpx.txt", httpx_output)
        progress.update(task, advance=1)

        response = fetch(base_url)
        progress.update(task, advance=1)

        header_report = analyze_headers(response)
        save_file(base, "headers.txt", header_report)
        if "MISSING" in header_report:
            findings.append({"name": "Header Misconfiguration", "score": 2})
        progress.update(task, advance=1)

        cookie_report = analyze_cookies(response)
        save_file(base, "cookies.txt", cookie_report)
        progress.update(task, advance=1)

        host_report = check_host_header(base_url)
        save_file(base, "host_header.txt", host_report)
        if "reflection" in host_report.lower():
            findings.append({"name": "Host Header Injection", "score": 3})
        progress.update(task, advance=1)

        error_report = check_error_handling(base_url)
        save_file(base, "error_test.txt", error_report)
        if "verbose" in error_report.lower():
            findings.append({"name": "Verbose Error Disclosure", "score": 2})
        progress.update(task, advance=1)

        robots_report = check_robots(base_url)
        save_file(base, "robots.txt", robots_report)
        progress.update(task, advance=1)

        sensitive_files = check_sensitive_files(base_url)
        save_file(base, "sensitive_files.txt", sensitive_files)
        if "No common" not in sensitive_files:
            findings.append({"name": "Sensitive File Exposure", "score": 4})
        progress.update(task, advance=1)

        graphql_result = check_graphql(base_url)
        save_file(base, "graphql.txt", graphql_result)
        progress.update(task, advance=1)

        swagger_result = check_swagger(base_url)
        save_file(base, "swagger.txt", swagger_result)
        progress.update(task, advance=1)

        dir_result = check_directory_listing(base_url)
        save_file(base, "directory_listing.txt", dir_result)
        progress.update(task, advance=1)

        sslscan_output = run_sslscan(target)
        save_file(base, "sslscan.txt", sslscan_output)
        progress.update(task, advance=1)

        nmap_output = run_nmap(target)
        save_file(base, "nmap.txt", nmap_output)
        progress.update(task, advance=1)

        # Screenshots
        screenshot_content(base_url, screenshots / "homepage.png", True)
        screenshot_content(f"<pre>{header_report}</pre>", screenshots / "headers.png")
        screenshot_content(f"<pre>{sslscan_output[:2000]}</pre>", screenshots / "sslscan.png")
        screenshot_content(f"<pre>{robots_report}</pre>", screenshots / "robots.png")
        screenshot_content(f"<pre>{nmap_output}</pre>", screenshots / "nmap.png")
        screenshot_content(f"<pre>{host_report}</pre>", screenshots / "host.png")
        screenshot_content(f"<pre>{error_report}</pre>", screenshots / "error.png")
        screenshot_content(f"<pre>{sensitive_files}</pre>", screenshots / "sensitive.png")
        screenshot_content(f"<pre>{graphql_result}</pre>", screenshots / "graphql.png")
        screenshot_content(f"<pre>{swagger_result}</pre>", screenshots / "swagger.png")

        progress.update(task, advance=1)

    risk_level, risk_score = calculate_risk(findings)

    images = {}
    for name in screenshots.glob("*.png"):
        images[name.name] = image_to_base64(name)

    html = f"""
    <html>
    <head>
    <style>
    body {{ font-family: Arial; background:#f4f4f4; padding:20px }}
    .card {{ background:white; padding:20px; margin-bottom:20px }}
    img {{ width:100%; margin-top:10px }}
    pre {{ background:#111; color:#0f0; padding:10px }}
    </style>
    </head>
    <body>

    <h1>Web Surface Security Review</h1>
    <h2>Target: {target}</h2>
    <h3>Risk Level: {risk_level} (Score: {risk_score})</h3>
    """

    for name, img in images.items():
        html += f"<div class='card'><h3>{name}</h3><img src='{img}'></div>"

    html += "</body></html>"

    save_file(base, "REPORT.html", html)

    console.print(f"[bold yellow]Risk Level: {risk_level} (Score: {risk_score})[/bold yellow]")
    console.print(f"[bold green]Completed. Output saved in {base}[/bold green]")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        console.print("[red]Usage: python3 auto_poc.py <target>[/red]")
        sys.exit(1)

    run_all(sys.argv[1])
