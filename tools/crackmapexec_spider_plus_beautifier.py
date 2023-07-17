#Developed by Tejas Pingulkar
import json
from colorama import Fore, Style, init

# Initialize colorama for Windows compatibility
init()

def print_tree(data, indent=0, parent_path="", color=Fore.YELLOW):
    for key, value in data.items():
        full_path = parent_path + "/" + key if parent_path else key

        if isinstance(value, dict):
            print("    " * indent + f"{color}{key}/")
            print_tree(value, indent + 1, parent_path=full_path, color=color)
        else:
            if key in ("size", "atime_epoch", "ctime_epoch", "mtime_epoch"):
                continue  # Skip printing these fields
            if parent_path:
                path_parts = parent_path.split("/")
                share_name = path_parts[0]
                path = "/".join(path_parts[1:])
                print("    " * indent + f"{Fore.YELLOW}{share_name}{Fore.WHITE}/{Fore.BLUE}{path}/{color}{key}")
            else:
                print("    " * indent + f"{color}{key}")

if __name__ == "__main__":
    file_path = input("Enter the path of the JSON data file: ")

    try:
        with open(file_path, 'r') as file:
            json_data = json.load(file)
    except FileNotFoundError:
        print("File not found.")
    except json.JSONDecodeError:
        print("Invalid JSON data.")
    else:
        print_tree(json_data)
