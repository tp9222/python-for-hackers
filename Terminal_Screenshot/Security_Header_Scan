import pyscreenshot
import os

with open('ip.txt') as f:
    while True:
        line = f.readline()
        if not line:
            break
        # To capture the screen
        os.system("clear")
        os.system("shcheck.py -d"+" "+"https://"+line )
        image = pyscreenshot.grab()

        # To display the captured screenshot
        #image.show()

        # To save the screenshot
        image.save(line, 'png')
        print(line.strip())
