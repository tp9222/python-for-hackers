import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import socket
import fcntl
import struct
import os

# Function to fetch the public IP address
def get_public_ip():
    try:
        response = requests.get('https://api.ipify.org?format=json')
        return response.json()['ip']
    except requests.RequestException:
        return "Unable to fetch public IP"

# Function to fetch the private IP address (from wlan0 or eth0)
def get_private_ip():
    try:
        # Get the name of the active network interface (wlan0 or eth0)
        interface = 'wlan0'  # Or 'eth0', depending on your preference
        private_ip = get_ip_address(interface)
        return private_ip
    except Exception as e:
        return f"Unable to fetch private IP: {str(e)}"

# Function to get IP address of a specific network interface
def get_ip_address(interface):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ip = fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', bytes(interface, 'utf-8')))
        return socket.inet_ntoa(ip[20:24])
    except Exception as e:
        return f"Error fetching IP for {interface}: {str(e)}"

# Function to send the email
def send_email():
    sender_email = "your_email@gmail.com"  # Replace with your sender email
    receiver_email = "receiver_email@example.com"  # Replace with the receiver's email
    password = "your_app_password"  # Replace with your app password (if using Gmail)

    # Fetch the public and private IP addresses
    public_ip = get_public_ip()
    private_ip = get_private_ip()

    # Create the email content
    subject = "Your System Information"
    body = f"Hello,\n\nYour system's current public IP address is: {public_ip}\n"
    body += f"Your system's current private IP address is: {private_ip}\n\nBest regards,\nYour system"
    
    # Setup the email MIME structure
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect to the SMTP server and send the email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()  # Secure the connection
            server.login(sender_email, password)  # Log in with your credentials
            server.sendmail(sender_email, receiver_email, msg.as_string())  # Send the email
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")

# Call the send_email function to send the email
send_email()
