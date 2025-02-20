import re
import csv

# Input and output file names
input_file = "whois_output.txt"
output_file = "whois_extracted.csv"

# Regex patterns for extracting IP and Organization Name
ip_pattern = re.compile(r"WHOIS for (\d+\.\d+\.\d+\.\d+):")
org_pattern = re.compile(r"OrgName:\s+(.+)")

# Store extracted data
data = []

# Read and extract data
with open(input_file, "r") as f:
    current_ip = None
    for line in f:
        ip_match = ip_pattern.search(line)
        org_match = org_pattern.search(line)
        
        if ip_match:
            current_ip = ip_match.group(1)
        
        if org_match and current_ip:
            org_name = org_match.group(1)
            data.append([current_ip, org_name])
            current_ip = None  # Reset for next entry

# Write to CSV
with open(output_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["IP Address", "Organization Name"])  # Header
    writer.writerows(data)

print(f"Extraction complete. Data saved in {output_file}")
