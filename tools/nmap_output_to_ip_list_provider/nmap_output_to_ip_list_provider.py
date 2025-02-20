import re

# Input and output file names
input_file = "nmap_input.txt"
output_file = "live_ips.txt"

# Read nmap scan results
with open(input_file, "r") as f:
    lines = f.readlines()

# Extract live IPs
live_ips = []
for line in lines:
    match = re.search(r"Nmap scan report for (\d+\.\d+\.\d+\.\d+)", line)
    if match:
        live_ips.append(match.group(1))

# Save live IPs to a file
with open(output_file, "w") as f:
    f.write("\n".join(live_ips))

print(f"Extracted {len(live_ips)} live IPs. Saved to {output_file}")
