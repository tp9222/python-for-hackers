import os
import xml.etree.ElementTree as ET

def process_nmap_output(file_path, output_file):
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
            for port_element in port_elements:
                portid = port_element.get('portid')
                protocol = port_element.get('protocol')
                service_element = port_element.find('.//service[@name]')
                service_name = service_element.get('name') if service_element is not None else "N/A"
                state_element = port_element.find('.//state[@state]')
                state = state_element.get('state') if state_element is not None else "N/A"
                output_file.write(f"\n   {protocol} / {portid} / {service_name} / {state}")

        output_file.write('\n\n')  # Two blank lines between IP outputs

if __name__ == "__main__":
    current_directory = os.getcwd()
    output_file_path = os.path.join(current_directory, "nmap_output.txt")

    with open(output_file_path, "w") as output_file:
        for file_name in os.listdir(current_directory):
            if file_name.endswith(".xml"):
                file_path = os.path.join(current_directory, file_name)
                process_nmap_output(file_path, output_file)

    print("Output written to nmap_output.txt")
