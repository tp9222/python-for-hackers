#!/usr/bin/env python3

import socket
import xml.etree.ElementTree as ET

target_ip = input("Enter target IP: ")
scan_type = input("Select scan type (1 for well-known ports, 2 for top 1000 ports, 3 for all ports): ")

ports = []

if scan_type == '1':
    ports = range(20, 1025)   # Well-known ports range
elif scan_type == '2':
    ports = [1,3,4,6,7,9,13,17,19,20,21,22,23,25,26,30,32,33,37,42,43,49,53,70,79,80,81,82,83,84,85,88,89,90,99,100,106,109,110,111,113,119,125,135,139,143,144,146,161,163,179,199,211,212,222,254,255,256,259,264,280,301,306,311,340,366,389,406,407,416,417,425,427,443,445,458,464,465,481,497,500,512,513,514,515,524,541,543,544,545,548,554,555,563,587,593,616,617,625,631,636,646,648,666,667,668,683,687,691,700,705,711,714,720,722,726,749,765,777,783,787,800,801,808,843,873,880,888,898,900,901,902,903,911,912,981,987,990,992,993,995,999,1000,1001,1002,1007,1009,1010,1011,1021,1022,1023,1024]   # Top 1000 ports range
else:
    ports = range(1, 65536)   # All ports range

scan_results = []

for port in ports:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex((target_ip, port))
    if result == 0:
        print(f"Port {port} is open")
        scan_results.append(port)
    sock.close()

output_xml = ET.Element('port_scan')

for port in scan_results:
    port_element = ET.SubElement(output_xml, 'port')
    ET.SubElement(port_element, 'number').text = str(port)
    ET.SubElement(port_element, 'status').text = 'open'

tree = ET.ElementTree(output_xml)
output_xml_file = f'port_scan_{scan_type}.xml'
tree.write(output_xml_file)

output_txt_file = f'port_scan_{scan_type}.txt'
with open(output_txt_file, 'w') as f:
    for port in scan_results:
        f.write(f'Port {port} is open\n')

print(f'Scan results saved in {output_xml_file} and {output_txt_file}')
