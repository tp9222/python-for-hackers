import pyscreenshot
import os
import colorama
from colorama import Fore

with open('ip.txt') as f:
    while True:
        line = f.readline()
        if not line:
            break
        # To capture the screen
        os.system("clear")
        print(Fore.RED + "Scan Running on IP Address: "+line)
        print(Fore.WHITE)
        os.system("nmap -p- -Pn -n -A -sC -sV --script vuln -oA "+line +" "+line)
        image = pyscreenshot.grab()

        # To display the captured screenshot
        #image.show()

        # To save the screenshot
        image.save(line, 'png')
        print(line.strip())
