import pyscreenshot
import os
import subprocess
import time

def run_command(command):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()
    return out, err

with open('ip.txt') as f:
    while True:
        line = f.readline().strip()
        if not line:
            break

        os.system("clear")
        command = "shcheck.py -d https://" + line

        # Run the command and capture its output
        command_output, _ = run_command(command)
        print(command_output.decode())  # Print the output of the command

        # Wait a bit to allow the command to complete fully
        time.sleep(2)  # Adjust the time delay as needed

        image = pyscreenshot.grab()

        # Modify the filename
        filename = "sec_header_" + line + ".png"
        
        # Save the screenshot
        image.save(filename)
        print(filename)
