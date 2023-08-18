import requests
import time
import random
from datetime import datetime

# Adjust the delay and randomized delay range based on your needs
BASE_DELAY_BETWEEN_REQUESTS = 5  # in seconds
RANDOM_DELAY_RANGE = (1, 5)  # Random delay between 1 to 5 seconds

def main():
    target_url = input("Enter the target website URL (e.g., https://www.example.com): ")
    
    try:
        with open("dork.txt", "r", encoding="utf-8") as dork_file:
            dorks = dork_file.readlines()
    except FileNotFoundError:
        print("Dork file 'dork.txt' not found.")
        return
    
    saved_results = []  # To store dorks with at least one result
    
    for dork in dorks:
        dork = dork.strip()
        search_url = f"https://www.google.com/search?q=site%3A{target_url}+{dork}"
        
        # Introduce randomized delay to avoid rate limiting
        delay = BASE_DELAY_BETWEEN_REQUESTS + random.randint(*RANDOM_DELAY_RANGE)
        time.sleep(delay)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        
        response = requests.get(search_url, headers=headers)
        
        if response.status_code == 200:
            # You can parse the response content to find relevant information
            if target_url in response.text:
                saved_results.append(dork)
    
    if saved_results:
        current_datetime = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        output_filename = f"dork_result_{current_datetime}.txt"
        
        with open(output_filename, "w") as output_file:
            output_file.write("Google dorks with at least one result:\n")
            for result in saved_results:
                output_file.write(result + "\n")
        
        print(f"Results saved to {output_filename}")
    else:
        print("No search results with at least one result were found.")

if __name__ == "__main__":
    main()
