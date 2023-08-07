import xml.etree.ElementTree as ET

def parse_nmap_output(xml_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        output = []

        for host in root.iter("host"):
            ip = host.find("address").get("addr")
            ports = []
            for port in host.iter("port"):
                port_id = port.get("portid")
                protocol = port.get("protocol")
                service = port.find("service").get("name")
                state = port.find("state").get("state")
                ports.append(f"{protocol} / {port_id} / {service} / {state}")
            output.append(f"{ip}\n   " + "\n   ".join(ports))

        return output

    except Exception as e:
        return ["Error:", str(e)]

def save_to_file(output):
    with open("nmap.output", "w") as f:
        f.write("\n\n".join(output))

if __name__ == "__main__":
    xml_file = input("Enter the Nmap XML file name: ")
    parsed_output = parse_nmap_output(xml_file)
    save_to_file(parsed_output)
    print("Output saved to nmap.output")
