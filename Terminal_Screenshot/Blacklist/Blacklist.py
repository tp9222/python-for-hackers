
import pyscreenshot
import os
import colorama
from colorama import Fore
import pydnsbl

with open('ip.txt') as f:
    while True:
        line = f.readline()
        if not line:
            break
        # To capture the screen
        os.system("clear")
        print(Fore.RED + "Scan Running on IP Address: "+line)
        print(Fore.WHITE)
        line=line.strip()
        ip_checker = pydnsbl.DNSBLIpChecker()
        RESULT=ip_checker.check(line)
        image = pyscreenshot.grab()
        if (RESULT.blacklisted)
          print(RESULT.blacklisted)
          print(RESULT.detected_by)

        # To display the captured screenshot
        #image.show()

        # To save the screenshot
        image.save(line, 'png')
        print(line.strip())

