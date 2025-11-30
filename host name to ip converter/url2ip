import csv
import socket
import sys
from collections import OrderedDict

def resolve_ips(domain):
    """Return a list of unique IPs (v4 and v6) for domain, preserving order."""
    try:
        results = socket.getaddrinfo(domain, None)
    except socket.gaierror:
        return ["Invalid URL"]
    ips = []
    for r in results:
        ip = r[4][0]
        if ip not in ips:
            ips.append(ip)
    return ips if ips else ["No records"]

def read_domains(input_file):
    """Read first column from CSV and return list of domains (skip empty)."""
    domains = []
    with open(input_file, newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            domain = row[0].strip()
            if domain:
                domains.append(domain)
    return domains

def main(input_file, output_file, join_char=','):
    domains = read_domains(input_file)

    # Keep insertion order and avoid duplicate domains
    unique_domains = list(OrderedDict.fromkeys(domains))

    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['URL', 'IP Addresses'])
        for domain in unique_domains:
            ips = resolve_ips(domain)
            # join IPs into one cell; if you prefer a different separator pass join_char
            writer.writerow([domain, join_char.join(ips)])

if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        print("Usage: python script_name.py <input_csv> <output_csv> [ip_separator]")
        print("Example: python script.py domains.csv domains_with_ips.csv \", \"")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    sep = sys.argv[3] if len(sys.argv) == 4 else ','

    main(input_file, output_file, sep)
