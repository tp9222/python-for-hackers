import csv
import base64

input_file = "creds.csv"
output_file = "encoded.txt"

with open(input_file, "r", encoding="utf-8") as csvfile:
    reader = csv.DictReader(csvfile)

    with open(output_file, "w", encoding="utf-8") as outfile:
        for row in reader:
            credentials = f"{row['Username'].strip()}:{row['Password'].strip()}"
            encoded = base64.b64encode(
                credentials.encode("utf-8")
            ).decode("utf-8")

            outfile.write(encoded + "\n")
            print(encoded)

print(f"\n[+] Saved to {output_file}")
