# Read IP addresses from a file (assuming one IP per line)
with open("ip_addresses.txt", "r") as file:
    ip_addresses = file.read().splitlines()

# Generate Rustscan commands for each IP address with output redirection
for ip in ip_addresses:
    rustscan_command = f"rustscan -a {ip} -- -Pn >> {ip}.txt"
    print(rustscan_command)
