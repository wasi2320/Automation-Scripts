import subprocess
import json
import requests

def send_to_google_chat(webhook_url, message_body):
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        'text': message_body
    }
    response = requests.post(webhook_url, headers=headers, json=data)
    return response.status_code, response.text

# def ExtractLinodesFirewalls():
#     firewalls = subprocess.check_output("linode-cli firewalls list --json", shell=True)
#     firewalls = json.loads(firewalls.decode())
#     for firewall in firewalls:
#         inboundRules = firewall['rules']['inbound']
#         for inboundRule in inboundRules:
#             ports = inboundRule['ports'].replace(" ", "").split(",")
#             addresses = inboundRule['addresses']['ipv4']
#             for address in addresses:
#                 if set(knownPorts).intersection(ports) and '0.0.0.0/0' in addresses:
#                     for port in ports:
#                         if port in knownPorts:
#                             # Format the violation message including firewall label, port, and IP range
#                             violation_message = f"Firewall: {firewall['label']} - Port: {port} - IP: {address}"
#                             violations.append(violation_message)

def ExtractLinodesFirewalls():
    firewalls = subprocess.check_output("linode-cli firewalls list --json", shell=True)
    firewalls = json.loads(firewalls.decode())
    for firewall in firewalls:
        inboundRules = firewall['rules']['inbound']
        for inboundRule in inboundRules:
            # Use .get() to handle cases where 'ports' might not exist
            ports = inboundRule.get('ports')
            if ports:  # Proceed only if ports exist
                ports = ports.replace(" ", "").split(",")
                addresses = inboundRule['addresses']['ipv4']
                for address in addresses:
                    if set(knownPorts).intersection(ports) and '0.0.0.0/0' in addresses:
                        for port in ports:
                            if port in knownPorts:
                                # Format the violation message including firewall label, port, and IP range
                                violation_message = f"Firewall: {firewall['label']} - Port: {port} - IP: {address}"
                                violations.append(violation_message)

                                
def format_google_chat_message(header, violations):
    formatted_message = f"{header}\n\n"
    
    # Add each violation as a bullet point
    for violation in violations:
        formatted_message += f"- {violation}\n"
    
    formatted_message += "\nKindly remove the access from respective firewalls. Thank you!"
    
    return formatted_message

#knownPorts = ["SSH","RDP","POSTGRES","ORACLE","MYSQL","REDIS","MONGODB","ALL PORTS"]
knownPorts = ["22", "2228", "3389", "8965", "5432", "7854", "1521", "7527", "3306", "4307", "6379", "27017", "1-65535"]
violations = []

ExtractLinodesFirewalls()

# Google Chat Webhook URL
google_chat_webhook_url = 'https://chat.googleapis.com/v1/spaces/AAAAVm58MNw/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=lavdyE8b_okfmb8KKAl_dwWHN424IvA-OkM9o9QvRh4'

# For Public Access
if violations:
    header = "*ALERT: Public Access in Linode Firewalls*"
    formatted_message = format_google_chat_message(header, violations)
    # Send the message to Google Chat
    status_code, response_text = send_to_google_chat(google_chat_webhook_url, formatted_message)