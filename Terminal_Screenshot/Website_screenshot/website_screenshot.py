import pyscreenshot # for screenshots
import os #for OS Commands
import colorama
from colorama import Fore 
from wakepy import set_keepawake, unset_keepawake # to prevent screen from lockout
from selenium import webdriver # to take web screccnshot
from PIL import Image # to take web screccnshot

# Here Chrome  will be used
driver = webdriver.Firefox()

with open('ip.txt') as f:
    while True:
        line = f.readline()
        if not line:
            break
        # To prevent screen from going to sleep
        #set_keepawake(keep_screen_awake=False)
		# Opening the website
        website="https://"+line
        driver.get(website)

        driver.save_screenshot(line)

        #release sleeplock
        #unset_keepawake()

        print(line.strip())
