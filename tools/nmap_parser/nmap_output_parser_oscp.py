import os
import xml.etree.ElementTree as ET

def process_nmap_output(file_path, output_file, port_list_file, nmap_command_file):
    tree = ET.parse(file_path)
    root = tree.getroot()

    host_elements = root.findall('.//host')
    for host_element in host_elements:
        address_element = host_element.find('.//address[@addr]')
        if address_element is not None:
            ip_address = address_element.get('addr')
            output_file.write(ip_address)
        else:
            output_file.write("IP Address not found\n")

        hostnames = host_element.findall('.//hostnames/hostname')
        if hostnames:
            domain = hostnames[0].get('name')
            output_file.write(f"\n{domain}\n")
        else:
            output_file.write("\n")

        port_elements = host_element.findall('.//ports/port')
        if port_elements:
            tcp_ports = []
            udp_ports = []
            for port_element in port_elements:
                portid = port_element.get('portid')
                protocol = port_element.get('protocol')
                if protocol == "tcp":
                    tcp_ports.append(portid)
                elif protocol == "udp":
                    udp_ports.append(portid)

                service_element = port_element.find('.//service[@name]')
                service_name = service_element.get('name') if service_element is not None else "N/A"
                state_element = port_element.find('.//state[@state]')
                state = state_element.get('state') if state_element is not None else "N/A"
                output_file.write(f"\n   {protocol} / {portid} / {service_name} / {state}")

            # Write the list of TCP and UDP ports to port_list_file
            port_list_file.write(f"{ip_address} TCP: {','.join(tcp_ports)} UDP: {','.join(udp_ports)}\n")

            # Add the nmap command to nmap_command_file
            nmap_command = f"nmap -oA {ip_address}_srv -sV -A -sC --script vuln -p {','.join(tcp_ports)} {ip_address}"
            nmap_command_file.write(f"{nmap_command}\n")

        output_file.write('\n\n')  # Two blank lines between IP outputs

if __name__ == "__main__":
    current_directory = os.getcwd()
    output_file_path = os.path.join(current_directory, "nmap_output.txt")
    port_list_file_path = os.path.join(current_directory, "port_list.txt")
    nmap_command_file_path = os.path.join(current_directory, "nmap_commands.txt")

    with open(output_file_path, "w") as output_file, open(port_list_file_path, "w") as port_list_file, open(nmap_command_file_path, "w") as nmap_command_file:
        for file_name in os.listdir(current_directory):
            if file_name.endswith(".xml"):
                file_path = os.path.join(current_directory, file_name)
                process_nmap_output(file_path, output_file, port_list_file, nmap_command_file)

    print("Output written to nmap_output.txt, port_list.txt, and nmap_commands.txt")
