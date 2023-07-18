import os
import threading

high_value_extensions = [
    ".csv", ".json", ".xls", ".xlsx", ".doc", ".docx", ".pdf", ".ppt", ".pptx",
    ".html", ".htaccess", ".properties", ".env", ".yml", ".yaml", ".py", ".php",
    ".asp", ".aspx", ".jsp", ".war", ".jar", ".gz", ".tar.gz", ".zip", ".rar",
    ".dbf", ".ini", ".rc", ".log", ".xml", ".pem", ".bak", ".backup", ".sql",
    ".conf", ".config", ".pbx", ".p12", ".old"
]

def search_files(path, output_file):
    with open(output_file, 'w', encoding='utf-8') as output:
        for root, dirs, files in os.walk(path):
            for file in files:
                if os.path.splitext(file)[1].lower() in high_value_extensions:
                    output.write(os.path.join(root, file) + '\n')

def search_files_thread(path, output_file):
    thread = threading.Thread(target=search_files, args=(path, output_file))
    thread.start()
    return thread

if __name__ == "__main__":
    search_path = input("Enter the path to search: ")
    output_file_name = input("Enter the output file name: ")

    threads = []

    for _ in range(5):  # Number of threads, you can adjust this as needed
        thread = search_files_thread(search_path, output_file_name)
        threads.append(thread)

    for thread in threads:
        thread.join()

    print("Search completed. Results saved in", output_file_name)
