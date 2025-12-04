#!/usr/bin/env python3
"""
website_screenshot.py

Bulk website screenshotter (Option A behavior):

- ip.txt entries do NOT include protocol.
- User provides a single --scheme (http or https) which is used for all generated URLs.
- If a line in ip.txt already includes a port (e.g. host:9000), that port is kept.
- If a line has no port, ports from --ports (-p) are applied; if --ports is empty, no port is appended.
- Selenium (Firefox) used by default with explicit geckodriver path (change --gecko if needed).
- Falls back to desktop screenshot (mss) if Selenium fails.
- Examples available via --help.

Example:
  echo "testserver" > ip.txt
  echo "internal-app:9000" >> ip.txt
  python3 website_screenshot.py -U ip.txt --scheme http -p 8080 --timeout 60 --out-dir shots
"""

import os
import re
import sys
import time
import argparse
from contextlib import suppress

DEFAULT_GECKO = "/usr/local/bin/geckodriver"

# optional keep-awake
try:
    from wakepy import keepawake
except Exception:
    keepawake = None

# selenium
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.common.exceptions import WebDriverException, TimeoutException

# ---------------------- helpers ----------------------

def parse_ports_spec(spec):
    """Parse '80', '80,443', '8000-8003' into sorted list of ints."""
    if not spec:
        return []
    parts = spec.split(",")
    ports = set()
    for part in parts:
        p = part.strip()
        if not p:
            continue
        if "-" in p:
            try:
                a, b = p.split("-", 1)
                a = int(a); b = int(b)
                if a > b:
                    a, b = b, a
                for x in range(a, b + 1):
                    if 1 <= x <= 65535:
                        ports.add(x)
            except Exception:
                continue
        else:
            try:
                x = int(p)
                if 1 <= x <= 65535:
                    ports.add(x)
            except Exception:
                continue
    return sorted(ports)

_RE_HOST_PORT = re.compile(r".+:\d+$")  # simple detection: ends with :<digits>

def host_has_port(host):
    """Return True if host string ends with :<port> (IPv6 brackets like [::1]:8000 are allowed)."""
    host = host.strip()
    # IPv6 with brackets: [::1]:8000 -> matches same regex
    return bool(_RE_HOST_PORT.search(host))

def safe_filename_from_url(url):
    s = (
        url.replace("://", "_")
           .replace("/", "_")
           .replace("?", "_")
           .replace("&", "_")
           .replace(":", "_")
    )
    return (s[:180] + ".png") if len(s) > 180 else s + ".png"

def ensure_parent(path):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)

# ---------------------- building targets ----------------------

def build_targets_for_host_option_a(host, ports, scheme, path=""):
    """
    Option A:
      - scheme is mandatory (http or https)
      - if host contains a port (e.g. host:9000), keep it exactly as-is
      - if host contains no port:
          - if ports list provided -> generate one URL per port: scheme://host:port
          - else -> single URL scheme://host (no added port)
      - path is appended verbatim
    """
    host = host.strip()
    if not host:
        return []

    # If host already includes a scheme, strip it (user should not include scheme)
    # But be permissive: if user accidentally included scheme, remove it and treat rest.
    if host.lower().startswith("http://") or host.lower().startswith("https://"):
        # user provided a full URL — keep as-is but normalize to chosen scheme
        # However Option A expects no protocol; if present we'll respect the explicit host:port provided.
        # We'll return the exact URL provided (append path).
        return [host.rstrip("/") + path]

    # If host already contains a port, preserve it
    if host_has_port(host):
        return [f"{scheme}://{host}{path}"]

    # No port in host
    urls = []
    if ports:
        for p in ports:
            urls.append(f"{scheme}://{host}:{p}{path}")
    else:
        urls.append(f"{scheme}://{host}{path}")
    return urls

# ---------------------- selenium init ----------------------

def init_firefox(headless=True, timeout=30, geckodriver_path=DEFAULT_GECKO, firefox_binary=None):
    opts = Options()
    if headless:
        opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")

    if firefox_binary:
        opts.binary_location = firefox_binary

    if not os.path.isfile(geckodriver_path):
        raise RuntimeError(f"geckodriver not found: {geckodriver_path}")
    if not os.access(geckodriver_path, os.X_OK):
        raise RuntimeError(f"geckodriver not executable: {geckodriver_path}")

    service = FirefoxService(executable_path=geckodriver_path)

    try:
        driver = webdriver.Firefox(service=service, options=opts)
        driver.set_page_load_timeout(timeout)
        return driver
    except WebDriverException as e:
        raise RuntimeError(f"Failed to start Firefox WebDriver: {e}")

# ---------------------- capture ----------------------

def capture_with_selenium(driver, url, out_file, wait=2.0, max_dim=20000):
    try:
        driver.get(url)
        time.sleep(wait)

        try:
            width = driver.execute_script(
                "return Math.max(document.body.scrollWidth, document.documentElement.scrollWidth);"
            )
            height = driver.execute_script(
                "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);"
            )
            width = min(int(width), max_dim)
            height = min(int(height), max_dim)
            driver.set_window_size(width, height)
            time.sleep(0.25)
        except Exception:
            pass

        if not driver.save_screenshot(out_file):
            raise RuntimeError("save_screenshot returned False")

        return True

    except TimeoutException as e:
        raise RuntimeError(f"Timeout loading {url}: {e}")
    except WebDriverException as e:
        raise RuntimeError(f"Selenium error on {url}: {e}")

def capture_with_mss(out_file):
    try:
        import mss, mss.tools
    except Exception as e:
        raise RuntimeError(f"mss not installed: {e}")

    with mss.mss() as s:
        mon = s.monitors[1]
        shot = s.grab(mon)
        mss.tools.to_png(shot.rgb, shot.size, output=out_file)
    return True

# ---------------------- main ----------------------

def main():
    parser = argparse.ArgumentParser(
        description="Bulk website screenshotter (Option A: single --scheme for all entries).",
        epilog="""
Examples:

  # ip.txt (no protocols):
  # testserver
  # internal-app:9000
  # api.example.com

  # Use HTTP for all generated URLs; if an ip.txt line already includes a port it's preserved:
  python3 website_screenshot.py -U ip.txt --scheme http -p 8080 --timeout 60 --out-dir shots

  # Use HTTPS for all generated URLs:
  python3 website_screenshot.py -U ip.txt --scheme https -p 8443
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--url-file", "-U", default="ip.txt",
                        help="File with hosts (no protocol). Default: ip.txt")
    parser.add_argument("--scheme", choices=["http", "https"], required=True,
                        help="Protocol to use for all generated URLs (http or https)")
    parser.add_argument("--ports", "-p", default="",
                        help="Ports to use for hosts without a port (single, comma list, ranges e.g. 80,8080-8082)")
    parser.add_argument("--out-dir", "-d", default="screenshots",
                        help="Directory to save screenshots")
    parser.add_argument("--wait", "-w", type=float, default=2.0,
                        help="Seconds to wait after page load before screenshot")
    parser.add_argument("--timeout", "-t", type=int, default=30,
                        help="Selenium page load timeout in seconds")
    parser.add_argument("--headless", action="store_true", default=True,
                        help="Run Firefox headless (default)")
    parser.add_argument("--no-headless", action="store_false", dest="headless",
                        help="Run Firefox with GUI")
    parser.add_argument("--no-selenium", action="store_true",
                        help="Disable Selenium; use desktop fallback only")
    parser.add_argument("--path", default="", help="Append path to generated URLs (e.g. /login)")
    parser.add_argument("--max-dim", type=int, default=20000, help="Max capture dimension")
    parser.add_argument("--gecko", default=DEFAULT_GECKO, help="Path to geckodriver binary")
    parser.add_argument("--firefox-binary", default=None, help="Path to Firefox binary if non-standard")

    args = parser.parse_args()

    ports = parse_ports_spec(args.ports)
    os.makedirs(args.out_dir, exist_ok=True)

    # read hosts file: allow comments and blank lines
    try:
        with open(args.url_file, "r", encoding="utf-8") as fh:
            raw = [ln.strip() for ln in fh if ln.strip() and not ln.strip().startswith("#")]
    except FileNotFoundError:
        print(f"File not found: {args.url_file}", file=sys.stderr)
        sys.exit(1)

    # build targets according to Option A
    targets = []
    for host in raw:
        targets.extend(build_targets_for_host_option_a(host, ports, args.scheme, path=args.path))

    if not targets:
        print("No targets generated. Check your url-file and --ports flag.", file=sys.stderr)
        sys.exit(1)

    print(f"[+] {len(targets)} targets generated; output -> {args.out_dir}")

    # init selenium
    driver = None
    if not args.no_selenium:
        try:
            driver = init_firefox(headless=args.headless, timeout=args.timeout,
                                  geckodriver_path=args.gecko, firefox_binary=args.firefox_binary)
        except Exception as e:
            print(f"[-] Selenium init failed: {e}", file=sys.stderr)
            driver = None

    AW = keepawake(keep_screen_on=True) if keepawake else None

    try:
        if AW:
            AW.__enter__()

        for idx, url in enumerate(targets, start=1):
            fname = f"{idx:03d}_{safe_filename_from_url(url)}"
            outpath = os.path.join(args.out_dir, fname)
            ensure_parent(outpath)

            print(f"[{idx}/{len(targets)}] {url}")

            captured = False

            if driver:
                try:
                    capture_with_selenium(driver, url, outpath, wait=args.wait, max_dim=args.max_dim)
                    print("  -> ok (selenium)")
                    captured = True
                except Exception as e:
                    print(f"  -> selenium failed: {e}", file=sys.stderr)

            if not captured:
                try:
                    capture_with_mss(outpath)
                    print("  -> ok (desktop fallback)")
                except Exception as e:
                    print(f"  -> fallback failed: {e}", file=sys.stderr)

        print("[+] Done.")
    finally:
        if AW:
            with suppress(Exception):
                AW.__exit__(None, None, None)
        if driver:
            with suppress(Exception):
                driver.quit()

if __name__ == "__main__":
    main()
