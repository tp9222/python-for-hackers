import os
import re

# Get the current folder path
folder_path = os.getcwd()

# Dictionary to store ports for each IP
ip_ports = {}

# Process each file in the folder
for file_name in os.listdir(folder_path):
    if file_name.endswith(".txt"):
        # Extract IP from the file name using a more robust regular expression
        match = re.match(r"(\d+\.\d+\.\d+\.\d+)", file_name)
        if match:
            ip = match.group(1)
            with open(os.path.join(folder_path, file_name), "r") as input_file:
                lines = input_file.readlines()
                # Extract open ports using regular expression
                open_ports = re.findall(r'Open (\S+)', "".join(lines))
                # Filter out close or filtered lines
                open_ports = [re.sub(r'.*?(\d+)$', r'\1', port) for port in open_ports]
                # Remove duplicate ports
                open_ports = list(set(open_ports))
                # Store open ports in the dictionary
                if ip not in ip_ports:
                    ip_ports[ip] = []
                ip_ports[ip].extend(open_ports)

# Create a summary file
with open("rust_out.txt", "w") as output_file:
    for ip, ports in ip_ports.items():
        output_file.write(f"{ip} --> {', '.join(ports)}\n")

print("Processing completed. Output saved to rust_out.txt.")
