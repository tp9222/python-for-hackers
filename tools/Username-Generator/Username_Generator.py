#Developer Tejas Pingulkar
import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import ttk
import itertools

def browse_input_file():
    file_path = filedialog.askopenfilename()
    input_file_entry.delete(0, tk.END)
    input_file_entry.insert(tk.END, file_path)

def browse_output_file():
    file_path = filedialog.asksaveasfilename(defaultextension=".txt")
    output_file_entry.delete(0, tk.END)
    output_file_entry.insert(tk.END, file_path)

def generate_usernames():
    input_file = input_file_entry.get().strip()
    output_file = output_file_entry.get().strip()

    if not input_file:
        messagebox.showerror("Error", "Please provide an input file.")
        return

    if not output_file:
        messagebox.showerror("Error", "Please provide an output file name.")
        return

    selected_formats = [var.get() for var in checkbox_vars]
    if sum(selected_formats) == 0:
        messagebox.showerror("Error", "Please select at least one username format.")
        return

    email_format = email_var.get()
    domain = domain_entry.get().strip()

    with open(input_file, 'r') as file:
        usernames = []
        for line in file:
            line = line.strip()
            if line:
                usernames.append(line)

    grouped_usernames = {}

    for username in usernames:
        grouped_usernames[username] = []
        for j, format_index in enumerate(selected_formats):
            if format_index == 1:
                generated_usernames = []
                if j == 0:
                    generated_usernames.append(f"u.{username.split()[1]}")
                elif j == 1:
                    generated_usernames.append(f"{username.split()[0]}.{username.split()[1]}")
                elif j == 2:
                    generated_usernames.append(f"{username.split()[1]}.u")
                elif j == 3:
                    generated_usernames.append(f"{username.split()[0]}.{username.split()[1]}")
                elif j == 4:
                    generated_usernames.append(f"u_{username.split()[1]}")
                elif j == 5:
                    generated_usernames.append(f"{username.split()[1]}.u")
                elif j == 6:
                    generated_usernames.append(f"{username.split()[0]}_{username.split()[1][-6:]}")
                elif j == 7:
                    generated_usernames.append(f"{username.split()[0]}_{username.split()[1][-2:]}")
                elif j == 8:
                    generated_usernames.append(f"{username.split()[0][:2]}_{username.split()[1]}")
                elif j == 9:
                    generated_usernames.append(f"{username.split()[0]}.{username.split()[1]}")
                elif j == 10:
                    generated_usernames.append(f"{username.split()[1]}_{username.split()[1]}")
                elif j == 11:
                    generated_usernames.append(f"{username.split()[1]}_{username.split()[0]}")
                elif j == 12:
                    generated_usernames.append(f"{username.split()[0][0]}{username.split()[1][0]}")
                elif j == 13:
                    generated_usernames.append(f"{username.split()[0][0]}.{username.split()[1][0]}")
                elif j == 14:
                    generated_usernames.append(f"{username.split()[0]}.{username.split()[1][0]}.{username.split()[1]}")
                elif j == 15:
                    generated_usernames.append(f"{username.split()[0]}_{username.split()[1]}_{username.split()[1]}")
                
                grouped_usernames[username].extend(generated_usernames)

    with open(output_file, 'w') as output:
        for username, generated_usernames in grouped_usernames.items():
            output.write(f"{username}:\n")
            if email_format == 1:
                email_usernames = [f"{username}@{domain}" for username in generated_usernames]
                output.write("  " + "\n  ".join(email_usernames) + "\n")
            else:
                output.write("  " + "\n  ".join(generated_usernames) + "\n")

    messagebox.showinfo("Success", "Usernames generated and saved successfully!")

window = tk.Tk()
window.title("Username Generator")

# Input File Entry
input_file_label = tk.Label(window, text="Input File:")
input_file_label.grid(row=0, column=0, sticky="e")
input_file_entry = tk.Entry(window)
input_file_entry.grid(row=0, column=1, padx=10, pady=5)
browse_input_button = tk.Button(window, text="Browse", command=browse_input_file)
browse_input_button.grid(row=0, column=2, padx=5, pady=5)

# Output File Entry
output_file_label = tk.Label(window, text="Output File:")
output_file_label.grid(row=1, column=0, sticky="e")
output_file_entry = tk.Entry(window)
output_file_entry.grid(row=1, column=1, padx=10, pady=5)
browse_output_button = tk.Button(window, text="Browse", command=browse_output_file)
browse_output_button.grid(row=1, column=2, padx=5, pady=5)

# Checkbox Options
checkbox_formats = [
    "u.surname",
    "username.surname",
    "surname.u",
    "firstname.surname",
    "u_lastname",
    "lastname.u",
    "firstname_lastsix",
    "firstname_lasttwo",
    "firsttwo_lastname",
    "firstname.lastname",
    "lastname_firstname",
    "lastname_firstname_initial",
    "firstname_lastname_initial",
    "firstname.middleinitial.lastname",
    "firstname_middlename_lastname"
]
checkbox_vars = []
for i, format_text in enumerate(checkbox_formats):
    var = tk.IntVar()
    checkbox = tk.Checkbutton(window, text=format_text, variable=var)
    checkbox.grid(row=i+2, column=0, columnspan=2, sticky="w")
    checkbox.select()  # Select all checkboxes by default
    checkbox_vars.append(var)

# Email Format Radio Button
email_var = tk.IntVar()
email_radio = tk.Radiobutton(window, text="Generate as email", variable=email_var, value=1)
email_radio.grid(row=len(checkbox_formats)+2, column=0, sticky="w")

# Domain Entry
domain_label = tk.Label(window, text="Domain:")
domain_label.grid(row=len(checkbox_formats)+3, column=0, sticky="e")
domain_entry = tk.Entry(window)
domain_entry.grid(row=len(checkbox_formats)+3, column=1, padx=10, pady=5)

# Generate Button
generate_button = tk.Button(window, text="Generate Usernames", command=generate_usernames)
generate_button.grid(row=len(checkbox_formats)+4, column=0, columnspan=2, pady=10)

window.mainloop()
