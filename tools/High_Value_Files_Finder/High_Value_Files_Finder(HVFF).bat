@echo off
setlocal

set "extensions=.csv .json .xls .xlsx .doc .docx .pdf .ppt .pptx .html .htaccess .properties .env .yml .yaml .py .php .asp .aspx .jsp .war .jar .gz .tar.gz .zip .rar .dbf .ini .rc .log .xml .pem .bak .backup .sql .conf .config .old"

for %%e in (%extensions%) do (
    dir /b /s "C:\path\to\search\*%%e"
)

endlocal
