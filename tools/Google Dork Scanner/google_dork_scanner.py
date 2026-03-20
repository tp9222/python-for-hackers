#!/usr/bin/env python3
"""
Google Dork Scanner
───────────────────
• Reads dorks from an external .txt file (one per line)
• Searches Google via requests + BeautifulSoup
• Adaptive rate-limit handling with auto pause / resume
• Saves structured results to a timestamped output file
• Supports resuming interrupted scans (tracks progress)
• Coloured terminal output for readability

Usage:
    python google_dork_scanner.py -t example.com -d dorks.txt [--min-wait 5 --max-wait 15] [-n 10]

Disclaimer:
    This tool is intended for authorised security research and educational
    purposes only.  Excessive automated queries may violate Google's Terms
    of Service.  Always obtain proper authorisation before scanning.
"""

import argparse
import csv
import json
import os
import random
import re
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print(
        "\n[!] Missing dependencies. Install them with:\n"
        "    pip install requests beautifulsoup4 lxml\n"
    )
    sys.exit(1)


# ──────────────────────────── ANSI colours ────────────────────────────
class C:
    HEADER  = "\033[95m"
    BLUE    = "\033[94m"
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RESET   = "\033[0m"


BANNER = rf"""
{C.CYAN}{C.BOLD}
  ╔══════════════════════════════════════════════════╗
  ║           GOOGLE DORK SCANNER v1.0               ║
  ║     Rate-Limited  •  Auto Resume  •  OSINT       ║
  ╚══════════════════════════════════════════════════╝
{C.RESET}
"""

# ──────────────────────── User-Agent rotation ─────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


# ──────────────────────── Progress / state file ───────────────────────
STATE_FILE = ".dork_scan_state.json"


def save_state(index: int, dork_file: str):
    """Persist progress so we can resume after interruption."""
    state = {"last_index": index, "dork_file": dork_file, "timestamp": datetime.now().isoformat()}
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def load_state(dork_file: str) -> int:
    """Return the index to resume from, or 0 if no saved state."""
    if not os.path.exists(STATE_FILE):
        return 0
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
        if state.get("dork_file") == dork_file:
            return state.get("last_index", 0) + 1  # start AFTER the last completed
        return 0
    except (json.JSONDecodeError, KeyError):
        return 0


def clear_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)


# ──────────────────────── Core search logic ───────────────────────────
class DorkScanner:
    GOOGLE_URL = "https://www.google.com/search"

    def __init__(
        self,
        pause_range: tuple[float, float] = (5.0, 12.0),
        num_results: int = 10,
        timeout: int = 15,
    ):
        self.pause_range = pause_range
        self.num_results = num_results
        self.timeout = timeout

        # Rate-limit state
        self.base_delay = pause_range[0]
        self.current_delay = self.base_delay
        self.max_delay = 300  # 5-minute cap
        self.backoff_factor = 2.0
        self.consecutive_ok = 0
        self.rate_limited_count = 0

        self.session = requests.Session()
        self._rotate_ua()

    # ── helpers ──
    def _rotate_ua(self):
        ua = random.choice(USER_AGENTS)
        self.session.headers.update(
            {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

    def _adaptive_wait(self):
        """Sleep for a random duration between user-defined min/max.
        During rate-limit backoff, the minimum is temporarily raised."""
        effective_min = max(self.pause_range[0], self.current_delay)
        effective_max = max(self.pause_range[1], self.current_delay * 1.5)
        wait = random.uniform(effective_min, effective_max)
        mins, secs = divmod(int(wait), 60)
        time_str = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
        print(
            f"  {C.DIM}⏳  Random wait: {time_str}  "
            f"(range {effective_min:.0f}s–{effective_max:.0f}s) …{C.RESET}",
            end="", flush=True,
        )

        # Live countdown
        remaining = wait
        while remaining > 0:
            chunk = min(remaining, 1.0)
            time.sleep(chunk)
            remaining -= chunk
        print("\r" + " " * 80 + "\r", end="", flush=True)

    def _handle_rate_limit(self):
        """Exponential back-off when Google returns 429 / CAPTCHA."""
        self.rate_limited_count += 1
        self.consecutive_ok = 0
        self.current_delay = min(self.current_delay * self.backoff_factor, self.max_delay)
        mins, secs = divmod(int(self.current_delay), 60)
        time_str = f"{mins}m {secs}s" if mins else f"{secs}s"
        print(
            f"\n  {C.RED}{C.BOLD}⚠  Rate-limited!{C.RESET}  "
            f"Backing off to {C.YELLOW}{time_str}{C.RESET} between requests  "
            f"(hit #{self.rate_limited_count})"
        )
        self._rotate_ua()  # switch fingerprint

    def _handle_success(self):
        """Gradually reduce delay back to user's min after rate-limit backoff."""
        self.consecutive_ok += 1
        if self.consecutive_ok >= 3 and self.current_delay > self.base_delay:
            old = self.current_delay
            self.current_delay = max(self.current_delay / 1.5, self.base_delay)
            print(
                f"  {C.GREEN}↓  Backoff eased: {old:.0f}s → {self.current_delay:.0f}s  "
                f"(recovering to {self.base_delay:.0f}s–{self.pause_range[1]:.0f}s range){C.RESET}"
            )
            self.consecutive_ok = 0

    # ── main search ──
    def search(self, dork: str, retries: int = 3) -> list[dict]:
        """
        Search Google for *dork* and return a list of result dicts:
        [{"title": ..., "url": ..., "snippet": ...}, ...]
        """
        params = {"q": dork, "num": self.num_results, "hl": "en", "start": 0}

        for attempt in range(1, retries + 1):
            try:
                resp = self.session.get(self.GOOGLE_URL, params=params, timeout=self.timeout)

                # ── Rate-limit / CAPTCHA detection ──
                if resp.status_code == 429 or "sorry" in resp.url.lower() or "captcha" in resp.text.lower():
                    self._handle_rate_limit()
                    if attempt < retries:
                        self._adaptive_wait()
                        continue
                    return [{"title": "RATE LIMITED", "url": "-", "snippet": "All retries exhausted"}]

                if resp.status_code != 200:
                    print(f"  {C.YELLOW}⚠  HTTP {resp.status_code} – retrying ({attempt}/{retries}){C.RESET}")
                    time.sleep(5)
                    continue

                self._handle_success()
                return self._parse_results(resp.text)

            except requests.exceptions.Timeout:
                print(f"  {C.YELLOW}⚠  Timeout – retrying ({attempt}/{retries}){C.RESET}")
                time.sleep(3)
            except requests.exceptions.ConnectionError as exc:
                print(f"  {C.RED}✗  Connection error: {exc}{C.RESET}")
                time.sleep(5)
            except Exception as exc:
                print(f"  {C.RED}✗  Unexpected error: {exc}{C.RESET}")
                break

        return []

    @staticmethod
    def _parse_results(html: str) -> list[dict]:
        """Extract title, URL, snippet from Google SERP HTML."""
        soup = BeautifulSoup(html, "lxml")
        results: list[dict] = []

        for g in soup.select("div.g, div[data-hveid]"):
            # Title + link
            anchor = g.select_one("a[href]")
            title_el = g.select_one("h3")
            if not anchor or not title_el:
                continue
            url = anchor.get("href", "")
            if not url.startswith("http"):
                continue
            title = title_el.get_text(strip=True)

            # Snippet
            snippet_el = (
                g.select_one("div[data-sncf]")
                or g.select_one("div.VwiC3b")
                or g.select_one("span.st")
                or g.select_one("div[style='-webkit-line-clamp:2']")
            )
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

            results.append({"title": title, "url": url, "snippet": snippet})

        return results


# ──────────────────────── Result writer ───────────────────────────────
class ResultWriter:
    """Write results in TXT and optional CSV formats."""

    def __init__(self, output_path: str, target: str = ""):
        self.txt_path = output_path
        self.csv_path = output_path.replace(".txt", ".csv")

        # Initialise files
        with open(self.txt_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*70}\n")
            f.write(f"  Google Dork Scan — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            if target:
                f.write(f"  Target: {target}\n")
            f.write(f"{'='*70}\n\n")

        write_header = not os.path.exists(self.csv_path) or os.path.getsize(self.csv_path) == 0
        self.csv_file = open(self.csv_path, "a", newline="", encoding="utf-8")
        self.csv_writer = csv.writer(self.csv_file)
        if write_header:
            self.csv_writer.writerow(["Timestamp", "Target", "Dork", "Title", "URL", "Snippet"])
        self.target = target

    def write(self, dork: str, results: list[dict]):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(self.txt_path, "a", encoding="utf-8") as f:
            f.write(f"[DORK]  {dork}\n")
            f.write(f"[TIME]  {ts}\n")
            if not results:
                f.write("  (no results)\n")
            for i, r in enumerate(results, 1):
                f.write(f"  {i}. {r['title']}\n")
                f.write(f"     {r['url']}\n")
                if r["snippet"]:
                    f.write(f"     {r['snippet'][:200]}\n")
            f.write(f"\n{'-'*70}\n\n")

        for r in results:
            self.csv_writer.writerow([ts, self.target, dork, r["title"], r["url"], r["snippet"]])
        self.csv_file.flush()

    def close(self):
        self.csv_file.close()


# ──────────────────────── Main entry point ────────────────────────────
def load_dorks(filepath: str) -> list[str]:
    """Read dorks from a text file, one per line. Skip blanks & comments."""
    path = Path(filepath)
    if not path.is_file():
        print(f"{C.RED}[!] Dork file not found: {filepath}{C.RESET}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        print(f"{C.RED}[!] Dork file is empty.{C.RESET}")
        sys.exit(1)
    return lines


def main():
    print(BANNER)

    parser = argparse.ArgumentParser(description="Google Dork Scanner with adaptive rate limiting")
    parser.add_argument("-t", "--target", required=True, help="Target domain to scan (e.g. example.com)")
    parser.add_argument("-d", "--dorks", required=True, help="Path to dorks .txt file (one per line)")
    parser.add_argument("-o", "--output", default=None, help="Output results file (default: results_<target>_<timestamp>.txt)")
    parser.add_argument("--min-wait", type=float, default=None, help="Minimum wait time between queries in seconds")
    parser.add_argument("--max-wait", type=float, default=None, help="Maximum wait time between queries in seconds")
    parser.add_argument("-n", "--num", type=int, default=10, help="Number of results per dork (default: 10)")
    parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout in seconds (default: 15)")
    parser.add_argument("--resume", action="store_true", help="Resume from last interrupted scan")
    parser.add_argument("--no-color", action="store_true", help="Disable coloured output")
    args = parser.parse_args()

    # Sanitise target domain (strip protocol, trailing slashes, whitespace)
    target = args.target.strip().lower()
    target = re.sub(r"^https?://", "", target)
    target = target.rstrip("/")

    # Disable colours if requested
    if args.no_color:
        for attr in vars(C):
            if not attr.startswith("_"):
                setattr(C, attr, "")

    # ── Ask user for min/max wait if not provided via CLI ──
    if args.min_wait is None or args.max_wait is None:
        print(f"  {C.BOLD}Configure random wait time between queries:{C.RESET}\n")
        while True:
            try:
                if args.min_wait is None:
                    raw = input(f"  {C.CYAN}Enter MINIMUM wait time (seconds) [default: 5]: {C.RESET}").strip()
                    args.min_wait = float(raw) if raw else 5.0
                if args.max_wait is None:
                    raw = input(f"  {C.CYAN}Enter MAXIMUM wait time (seconds) [default: 15]: {C.RESET}").strip()
                    args.max_wait = float(raw) if raw else 15.0

                if args.min_wait < 0 or args.max_wait < 0:
                    print(f"  {C.RED}Wait times must be positive numbers.{C.RESET}")
                    args.min_wait = args.max_wait = None
                    continue
                if args.min_wait > args.max_wait:
                    print(f"  {C.RED}Minimum ({args.min_wait}s) cannot be greater than maximum ({args.max_wait}s).{C.RESET}")
                    args.min_wait = args.max_wait = None
                    continue
                break
            except ValueError:
                print(f"  {C.RED}Please enter valid numbers.{C.RESET}")
                args.min_wait = args.max_wait = None
        print()

    min_wait = args.min_wait
    max_wait = args.max_wait

    # Output file
    if args.output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_target = re.sub(r"[^a-zA-Z0-9._-]", "_", target)
        args.output = f"results_{safe_target}_{ts}.txt"

    dorks = load_dorks(args.dorks)
    total = len(dorks)

    # Resume logic
    start_idx = 0
    if args.resume:
        start_idx = load_state(args.dorks)
        if start_idx > 0:
            print(f"  {C.GREEN}↻  Resuming from dork #{start_idx + 1} / {total}{C.RESET}\n")
        else:
            print(f"  {C.DIM}(no saved state found – starting fresh){C.RESET}\n")

    print(f"  {C.BOLD}Target     :{C.RESET}  {C.RED}{target}{C.RESET}")
    print(f"  {C.BOLD}Dork file  :{C.RESET}  {args.dorks}  ({total} dorks)")
    print(f"  {C.BOLD}Output     :{C.RESET}  {args.output}  (+{args.output.replace('.txt', '.csv')})")
    print(f"  {C.BOLD}Wait range :{C.RESET}  {min_wait}s – {max_wait}s  (randomised)")
    print(f"  {C.BOLD}Results/q  :{C.RESET}  {args.num}")
    print()

    # ── Prepend site:<target> to each dork ──
    # If a dork already contains a site: operator, replace it with the target
    site_re = re.compile(r"\bsite:\S+", re.IGNORECASE)
    targeted_dorks = []
    for dork in dorks:
        if site_re.search(dork):
            # Replace any existing site: with the target
            dork_clean = site_re.sub("", dork).strip()
            targeted_dorks.append(f"site:{target} {dork_clean}")
        else:
            targeted_dorks.append(f"site:{target} {dork}")
    dorks = targeted_dorks

    scanner = DorkScanner(
        pause_range=(min_wait, max_wait),
        num_results=args.num,
        timeout=args.timeout,
    )
    writer = ResultWriter(args.output, target=target)

    total_results = 0

    # Graceful Ctrl+C
    def sig_handler(sig, frame):
        print(f"\n\n  {C.YELLOW}⏸  Interrupted! Progress saved. Use --resume to continue.{C.RESET}\n")
        writer.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)

    # ── Scan loop ──
    for idx in range(start_idx, total):
        dork = dorks[idx]
        pct = (idx + 1) / total * 100
        print(
            f"  {C.BOLD}[{idx + 1}/{total}]{C.RESET}  "
            f"{C.CYAN}{dork}{C.RESET}  "
            f"{C.DIM}({pct:.0f}%){C.RESET}"
        )

        results = scanner.search(dork)

        if results:
            total_results += len(results)
            for r in results:
                domain = urlparse(r["url"]).netloc
                print(f"    {C.GREEN}→{C.RESET}  {r['title'][:70]}")
                print(f"       {C.BLUE}{domain}{C.RESET}")
        else:
            print(f"    {C.DIM}(no results){C.RESET}")

        writer.write(dork, results)
        save_state(idx, args.dorks)

        # Don't wait after the last dork
        if idx < total - 1:
            scanner._adaptive_wait()

    # ── Summary ──
    writer.close()
    clear_state()

    print(f"\n  {C.GREEN}{C.BOLD}✓  Scan complete!{C.RESET}")
    print(f"  {C.BOLD}Target        :{C.RESET}  {target}")
    print(f"  {C.BOLD}Dorks scanned :{C.RESET}  {total - start_idx}")
    print(f"  {C.BOLD}Total results :{C.RESET}  {total_results}")
    print(f"  {C.BOLD}Wait range    :{C.RESET}  {min_wait}s – {max_wait}s")
    print(f"  {C.BOLD}Rate limits   :{C.RESET}  {scanner.rate_limited_count}")
    print(f"  {C.BOLD}Results saved :{C.RESET}  {args.output}")
    print(f"  {C.BOLD}CSV saved     :{C.RESET}  {args.output.replace('.txt', '.csv')}")
    print()


if __name__ == "__main__":
    main()
