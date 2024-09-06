import ipaddress
import subprocess
import platform

def ping_ip(ip):
    # Determine the command based on the OS
    param = "-n" if platform.system().lower() == "windows" else "-c"
    
    # Ping the IP address
    command = ["ping", param, "1", "-W", "1", str(ip)]
    response = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    return response.returncode == 0

def check_active_ips(ip_range):
    # Parse the IP range
    try:
        network = ipaddress.ip_network(ip_range, strict=False)
    except ValueError:
        print("Invalid IP range format. Please enter a valid CIDR notation (e.g., 192.168.1.0/24).")
        return
    
    active_ips = []
    
    print(f"Checking active IPs in range: {network}")
    
    # Iterate over all hosts in the network
    for ip in network.hosts():
        if ping_ip(ip):
            print(f"{ip} is active.")
            active_ips.append(str(ip))
    
    if not active_ips:
        print("No active IPs found.")
    else:
        print("\nActive IPs found:")
        for active_ip in active_ips:
            print(active_ip)

if __name__ == "__main__":
    # Take IP range input from the user
    ip_range = input("Enter the IP range in CIDR notation (e.g., 192.168.1.0/24): ")
    check_active_ips(ip_range)
