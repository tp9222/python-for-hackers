# CSV Credentials to Base64 Encoder

A small Python utility that reads usernames and passwords from a CSV
file, encodes each `username:password` pair using Base64, and writes the
encoded values to a text file.

The output contains **only the Base64-encoded values**, one per line. It
does not add the `Authorization: Basic` prefix.

## Features

-   Reads credentials from `creds.csv`.
-   Encodes each `username:password` pair using UTF-8 and Base64.
-   Prints encoded values to the terminal.
-   Saves encoded values to `encoded.txt`.
-   Produces one encoded value per input row.

## Requirements

-   Python 3
-   No third-party Python packages required.

## Input CSV format

Create a file named `creds.csv` with the following column names:

``` csv
Username,Password
admin,admin
testuser,password123
```

The column names must be `Username` and `Password`.

## Usage

1.  Save the Python script as `encode_credentials.py`.

2.  Place `creds.csv` in the same directory.

3.  Run:

    ``` bash
    python3 encode_credentials.py
    ```

4.  The encoded values will be:

    -   Printed in the terminal.
    -   Saved to `encoded.txt`.

## Example

For this input:

``` csv
Username,Password
admin,admin
```

The output is:

``` text
YWRtaW46YWRtaW4=
```

This is the Base64 encoding of:

``` text
admin:admin
```

## Output format

The output file contains only encoded values:

``` text
<base64-value-1>
<base64-value-2>
<base64-value-3>
```

It does not contain an HTTP header such as `Authorization: Basic`.

## Security considerations

-   **Base64 is encoding, not encryption.** Anyone who obtains an
    encoded value can decode it.

-   Do not commit real usernames, passwords, `creds.csv`, or generated
    credential files to a public GitHub repository.

-   Add sensitive files to `.gitignore`:

    ``` gitignore
    creds.csv
    encoded.txt
    ```

-   Use Basic Authentication only over HTTPS.

-   Use this utility only with credentials you are authorized to handle.

## License

Choose and add a license before distributing or reusing this project
publicly.
