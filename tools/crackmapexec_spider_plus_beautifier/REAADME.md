This Python script takes the raw output of CrackMapExec (CME) and beautifies it by representing the share names, paths, and filenames in a tree-like format with color-coded output for better readability. The script uses the colorama library to provide colored output on both Windows and Unix-based systems.

**Features**

    Beautifies the CrackMapExec raw output by representing shares, paths, and filenames in a tree-like format.
    Provides color-coded output to differentiate between share names, paths, and filenames.

**How to Use**
    Ensure you have Python 3.x installed on your system.
    Install the colorama library using pip:

    pip install colorama

    Run the script:
    python crackmap_beautifier.py

**Note**
  Make sure to have the CrackMapExec raw output JSON data file in the required format. The script may not work correctly if the JSON structure differs.
