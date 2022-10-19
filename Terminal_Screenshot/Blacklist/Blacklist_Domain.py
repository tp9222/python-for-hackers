import pyscreenshot #screenshots
import os # OS commands
import colorama # color output
from colorama import Fore # color output
import pydnsbl # black list idenfification
import json 

blacklisted_list={}

with open('ip.txt') as f:
    while True:
        line = f.readline()
        if not line:
            break
        # To capture the screen
        os.system("clear")
        
        #display current IP in red title

        print(Fore.RED + "Scan Running on IP Address: "+line)
        print(Fore.WHITE)

        #Remove newline character

        line=line.strip()
        
        #blacklist validation

        domain_checker = pydnsbl.DNSBLDomainChecker()
        RESULT=domain_checker.check(line)
        image = pyscreenshot.grab()

        #if IP blacklisted then write to file

        if (RESULT.blacklisted):
          print(RESULT.blacklisted)
          print(RESULT.detected_by)
          blacklisted_list=(RESULT.detected_by)
          write_to_file = open("blacklist.txt", "a")
          write_to_file.writelines("\nblacklisted Domain: "+line)
          write_to_file.write("\nBlacklisted By:")
          write_to_file.write(json.dumps(blacklisted_list))
          write_to_file.writelines("\n------------------------")
          write_to_file.close()
        # To display the captured screenshot
        #image.show()

        # To save the screenshot
        image.save(line, 'png')
        print(line.strip())
