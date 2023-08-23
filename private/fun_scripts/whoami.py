import time
import sys

def print_typing(text, delay=0.05):
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def print_stylized_info():
    print_stylized_line("\033[1;32;40m>whoami\033[1;37;40m")
    print_stylized_line("\033[1;32;40mName:\033[1;37;40m Tejas Pingulkar")
    print_stylized_line("\033[1;32;40mExperience:\033[1;37;40m 8 Years Network, Web application, Thick Client, iOS & Android Pentest")
    print_stylized_line("\033[1;32;40mCVE:\033[1;37;40m CVE-2020-13480, CVE-2020-11561, CVE-2020-27416, CVE-2022-47075, CVE-2022-47076")

def print_stylized_line(line):
    print_typing(line, delay=0.05)

if __name__ == "__main__":
    #print("\033[1;31;40mHacker Terminal\033[0m")
    print_stylized_info()
