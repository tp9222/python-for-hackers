import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

APT_PACKAGES = [
    "nmap",
    "sslscan",
    "whois",
    "curl",
    "openssl",
    "wkhtmltopdf",
    "imagemagick",
    "jq",
    "golang"
]

GO_TOOLS = {
    "httpx": "github.com/projectdiscovery/httpx/cmd/httpx@latest",
    "nuclei": "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
}

CARGO_TOOLS = ["rustscan"]


def run(cmd):
    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True
    )
    if result.returncode != 0:
        print(f"\n[ERROR] {cmd}")
        print(result.stderr.strip())


def exists(binary):
    return shutil.which(binary) is not None


def install_all():
    run("sudo apt update")
    run("sudo apt install -y " + " ".join(APT_PACKAGES))

    if not exists("rustc"):
        run("curl https://sh.rustup.rs -sSf | sh -s -- -y")

    for module in GO_TOOLS.values():
        run(f"go install {module}")

    for tool in CARGO_TOOLS:
        run(f"$HOME/.cargo/bin/cargo install {tool} --locked")

    run("nuclei -update-templates")


if __name__ == "__main__":
    print("Installing dependencies...")
    install_all()
    print("Setup completed.")
