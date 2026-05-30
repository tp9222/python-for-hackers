# High Value Files Finder (HVFF)

Multi-platform tool for recursively searching a filesystem for high-value file types commonly targeted during penetration testing — credentials, config files, keys, archives, source code, and database files.

---

## Scripts

| Script | Platform | Description |
|---|---|---|
| `High_Value_Files_Finder(HVFF).py` | Cross-platform | Threaded Python scanner — saves results to a specified output file |
| `High_Value_Files_Finder(HVFF).bat` | Windows | Batch script using `dir /b /s` |
| `High_Value_Files_Finder.sh` | Linux/macOS | Single `find` command covering all extensions |

---

## File Types Searched

`.csv .json .xls .xlsx .doc .docx .pdf .ppt .pptx .html .htaccess .properties .env .yml .yaml .py .php .asp .aspx .jsp .war .jar .gz .tar.gz .zip .rar .dbf .ini .rc .log .xml .pem .bak .backup .sql .conf .config .pbx .p12 .old`

---

## Requirements

- Python 3.8+ — stdlib only, no external packages required.
- Windows `.bat`: Windows CLI
- Shell script: `find` utility (standard on Linux/macOS)

---

## Usage

### Python (recommended — cross-platform, threaded)

```bash
python3 "High_Value_Files_Finder(HVFF).py"
# Enter the path to search: /home/user
# Enter the output file name: hvff_results.txt
```

### Linux / macOS

Edit the path in the script, then:

```bash
chmod +x High_Value_Files_Finder.sh
./High_Value_Files_Finder.sh
```

Or run inline with a custom path:

```bash
find /target/path -type f \( -iname "*.env" -o -iname "*.pem" -o -iname "*.sql" \)
```

### Windows (Batch)

Edit `C:\path\to\search\` in the `.bat` file, then double-click or run from CMD:

```cmd
High_Value_Files_Finder(HVFF).bat
```

---

## Notes

- The Python script uses 5 threads by default. Increase or decrease the thread count in the script for performance tuning.
- All 5 threads write to the same output file — results may interleave. Sort or deduplicate after if needed.
- On Linux, the shell script is typically faster than the Python version for local filesystem scans.
- During a pentest, useful search paths include: `C:\`, `/home`, `/var/www`, `/opt`, `/etc`, network shares.

---

## Disclaimer

For authorised penetration testing and security research only.
