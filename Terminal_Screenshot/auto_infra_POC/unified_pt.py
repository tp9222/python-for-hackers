import os
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

IP_FILE = "ip.txt"
BASE_DIR = "scan_results"
MAX_WORKERS = 2

# Create unique parent folder per run
RUN_ID = "PT_" + datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_DIR = os.path.join(BASE_DIR, RUN_ID)

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


# -----------------------------
# Utility Functions
# -----------------------------

def highlight_line(line):
    l = line.lower()

    if "error" in l or "failed" in l:
        return RED + line + RESET

    if "/tcp" in l and "open" in l:
        return GREEN + line + RESET

    if "critical" in l or "high" in l:
        return RED + line + RESET

    if "medium" in l:
        return YELLOW + line + RESET

    if "vulnerable" in l or "weak" in l:
        return RED + line + RESET

    return line


def run_command(cmd, output_file):
    print(f"\n{BLUE}Running: {cmd}{RESET}")

    with open(output_file, "w") as out:
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        for line in process.stdout:
            out.write(line)
            print(highlight_line(line), end="")

        process.wait()

    return process.returncode


def generate_screenshot(text_file, png_file):
    html_tmp = text_file + ".html"

    with open(text_file, "r", errors="ignore") as f:
        content = f.read()

    safe_content = (
        content.replace("&", "&amp;")
               .replace("<", "&lt;")
               .replace(">", "&gt;")
    )

    html_content = f"""
    <html>
    <body style="background:black;color:#00ff00;font-family:monospace;padding:20px;">
    <pre>{safe_content}</pre>
    </body>
    </html>
    """

    with open(html_tmp, "w") as f:
        f.write(html_content)

    subprocess.run(
        f"wkhtmltoimage --width 1200 {html_tmp} {png_file}",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    os.remove(html_tmp)


def parse_nmap_output(file_path):
    open_ports = []
    http = False
    https = False

    with open(file_path, "r", errors="ignore") as f:
        for line in f:
            if "/tcp" in line and "open" in line:
                port = line.split("/")[0].strip()
                open_ports.append(port)

                if port == "80":
                    http = True
                if port == "443":
                    https = True

    return open_ports, http, https


# -----------------------------
# Report Generation
# -----------------------------

def generate_target_report(target, target_dir, open_ports):
    screenshot_dir = os.path.join(target_dir, "screenshots")
    report_path = os.path.join(target_dir, "report.html")

    screenshots_html = ""
    if os.path.exists(screenshot_dir):
        for img in os.listdir(screenshot_dir):
            screenshots_html += f"<h3>{img}</h3>"
            screenshots_html += f"<img src='screenshots/{img}' style='width:100%;margin-bottom:30px;'>"

    ports_html = "".join(f"<li>{p}</li>" for p in open_ports)
    if not ports_html:
        ports_html = "<li>No open ports detected</li>"

    html_content = f"""
    <html>
    <body style="background:#111;color:#eee;font-family:Arial;padding:30px;">
    <h1>Scan Report - {target}</h1>

    <h2>Open Ports</h2>
    <ul>{ports_html}</ul>

    <h2>Scan Evidence</h2>
    {screenshots_html}

    </body>
    </html>
    """

    with open(report_path, "w") as f:
        f.write(html_content)


def generate_master_report():
    master_path = os.path.join(RUN_DIR, "master_report.html")
    links = ""

    for target in os.listdir(RUN_DIR):
        target_dir = os.path.join(RUN_DIR, target)
        if os.path.isdir(target_dir):
            links += f"<li><a href='{target}/report.html'>{target}</a></li>"

    html_content = f"""
    <html>
    <body style="background:black;color:#00ff00;font-family:monospace;padding:40px;">
    <h1>Network PT Master Report</h1>
    <h2>Engagement ID: {RUN_ID}</h2>
    <ul>{links}</ul>
    </body>
    </html>
    """

    with open(master_path, "w") as f:
        f.write(html_content)

    print(f"\nMaster report generated at: {master_path}")


# -----------------------------
# Scan Logic
# -----------------------------

def scan_target(target, scan_mode):
    print(f"\n{'='*60}")
    print(f"{BLUE}Scanning Target: {target}{RESET}")
    print(f"{'='*60}")

    target_dir = os.path.join(RUN_DIR, target)
    screenshot_dir = os.path.join(target_dir, "screenshots")

    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(screenshot_dir, exist_ok=True)

    if scan_mode == "fast":
        nmap_cmd = f"nmap -sC -sV --top-ports 1000 -T4 -Pn {target}"
    else:
        nmap_cmd = f"nmap -sC -sV -p- -T4 -Pn {target}"

    nmap_output = os.path.join(target_dir, "nmap.txt")
    run_command(nmap_cmd, nmap_output)
    generate_screenshot(nmap_output, os.path.join(screenshot_dir, "nmap.png"))

    open_ports, http, https = parse_nmap_output(nmap_output)

    if not open_ports:
        print(f"{YELLOW}No open ports detected. Generating minimal report.{RESET}")
        generate_target_report(target, target_dir, open_ports)
        print(f"\n{GREEN}[{target}] Completed{RESET}\n")
        return

    if https:
        ssl_output = os.path.join(target_dir, "sslscan.txt")
        run_command(f"sslscan {target}:443", ssl_output)
        generate_screenshot(ssl_output, os.path.join(screenshot_dir, "sslscan.png"))

    if http or https:
        nuclei_output = os.path.join(target_dir, "nuclei.txt")
        run_command(f"echo {target} | nuclei -severity low,medium,high,critical", nuclei_output)
        generate_screenshot(nuclei_output, os.path.join(screenshot_dir, "nuclei.png"))

    generate_target_report(target, target_dir, open_ports)

    print(f"\n{GREEN}[{target}] Completed{RESET}\n")


# -----------------------------
# Main
# -----------------------------

def main():
    if not os.path.exists(IP_FILE):
        print("ip.txt not found")
        return

    os.makedirs(RUN_DIR, exist_ok=True)

    print("\n1 → Fast Scan")
    print("2 → Full Scan")
    choice = input("Select: ").strip()

    if choice == "1":
        scan_mode = "fast"
    elif choice == "2":
        scan_mode = "full"
    else:
        print("Invalid choice.")
        return

    with open(IP_FILE) as f:
        targets = [x.strip() for x in f if x.strip()]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(scan_target, t, scan_mode) for t in targets]
        for _ in as_completed(futures):
            pass

    generate_master_report()

    print(f"\n{GREEN}All scans completed successfully.{RESET}")
    print(f"{GREEN}Engagement Folder: {RUN_DIR}{RESET}\n")


if __name__ == "__main__":
    main()
