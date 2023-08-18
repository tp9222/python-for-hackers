import webbrowser
import time
import random

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
        
        response = webbrowser.open_new_tab(search_url)
        
        if response:
            saved_results.append(dork)
    
    if saved_results:
        print("Search tabs opened for Google dorks with at least one result:")
        for result in saved_results:
            print(result)
    else:
        print("No search results with at least one result were found.")

if __name__ == "__main__":
    main()
