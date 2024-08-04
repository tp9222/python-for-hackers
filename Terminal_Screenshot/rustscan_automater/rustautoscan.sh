#!/bin/bash

# Loop through each IP in ip.txt
while IFS= read -r ip; do
    # Run rustscan on the current IP and save the output to a file named after the IP
    rustscan -a "$ip" -u 5000 -b 1000 -- -A -sV > "${ip}.txt"
done < ip.txt
