import pyscreenshot
import os
import colorama
from colorama import Fore
from wakepy import set_keepawake, unset_keepawake


with open('ip.txt') as f:
    while True:
        line = f.readline()
        if not line:
            break
        # To prevent screen from going to sleep
        set_keepawake(keep_screen_awake=False)
        # To capture the screen
        os.system("clear")

        #Print title in red color
        print(Fore.RED + "Scan Running on IP Address: "+line)
        
        #Print output in white color
        print(Fore.WHITE)
        
        #remove /n from target line
        line=line.strip()

        command=("nmap -p- -Pn -n -A -sC -sV --script vuln "+line +" -oA "+ line)
        print(command)
        os.system(command)
        image = pyscreenshot.grab()

        # To display the captured screenshot
        #image.show()

        # To save the screenshot
        line="nmap_"+line;
        image.save(line, 'png')

        #release sleeplock
        unset_keepawake()
        
        print(line.strip())
