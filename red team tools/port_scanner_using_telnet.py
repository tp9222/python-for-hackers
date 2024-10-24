import telnetlib
import socket

ports = [21, 22, 23, 445, 80, 443]

with open('ip.txt', 'r') as file:
    ip_list = file.read().splitlines()

for ip in ip_list:
    for port in ports:
        try:
            telnetlib.Telnet(ip, port, timeout=2)
            print(f"{ip}:{port} open")
        except (socket.timeout, ConnectionRefusedError, OSError):
            pass