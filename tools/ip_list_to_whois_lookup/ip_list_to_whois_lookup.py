import subprocess

# Input and output file names
input_file = "ip_list.txt"
output_file = "whois_output.txt"

# Read IPs from file
with open(input_file, "r") as f:
    ip_list = [line.strip() for line in f if line.strip()]

# Perform WHOIS lookup and save results
with open(output_file, "w") as f:
    for ip in ip_list:
        try:
            result = subprocess.run(["whois", ip], capture_output=True, text=True, timeout=10)
            f.write(f"WHOIS for {ip}:\n{result.stdout}\n{'='*50}\n")
            print(f"Processed WHOIS for {ip}")
        except Exception as e:
            f.write(f"Error fetching WHOIS for {ip}: {e}\n{'='*50}\n")
            print(f"Error processing {ip}: {e}")

print(f"WHOIS lookup completed. Results saved in {output_file}")
