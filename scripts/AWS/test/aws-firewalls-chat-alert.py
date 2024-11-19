import boto3
import requests, ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import awsAccounts

def get_security_group_details(credentials, account_name):

    # Set the region based on account_name
    region = 'us-east-2' if account_name == 'Glaukos' else 'us-east-1'

    session = boto3.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )
    ec2 = session.client('ec2')
    security_groups = ec2.describe_security_groups()

    check_inbound_rules(security_groups, account_name)
    check_prod_inbound_rules(security_groups, account_name)


def check_inbound_rules(security_groups, account_name):
    for security_group in security_groups['SecurityGroups']:
        for rule in security_group['IpPermissions']:
            # Check if the rule is for any of the known ports
            from_port = str(rule.get('FromPort', ''))
            to_port = str(rule.get('ToPort', ''))
            
            if from_port in known_ports or to_port in known_ports:
                # Check the IP ranges for '0.0.0.0/0'
                for ip_range in rule.get('IpRanges', []):
                    if ip_range.get('CidrIp') in ['0.0.0.0/0', '::/0']:
                        port = from_port if from_port in known_ports else to_port
                        violation_message = f"Account: {account_name} - SG ID: {security_group['GroupId']} - Port: {port} - IP: {ip_range.get('CidrIp')}"
                        violations.append(violation_message)

                # Check IPv6 ranges for '::/0' 
                for ip_range in rule.get('Ipv6Ranges', []):
                    if ipaddress.IPv6Network(ip_range.get('CidrIpv6')) == ipaddress.IPv6Network('::/0'):  # Check for IPv6 equivalence
                        port = from_port if from_port in known_ports else to_port
                        violation_message = f"Account: {account_name} - SG ID: {security_group['GroupId']} - Port: {port} - IP: {ip_range.get('CidrIpv6')}"
                        violations.append(violation_message)


def check_prod_inbound_rules(security_groups, account_name):
    for security_group in security_groups['SecurityGroups']:
        # Check if the security group has the tag key "Environment" with value "Prod"
        tags = {tag['Key']: tag['Value'] for tag in security_group.get('Tags', [])}
        if tags.get('Environment') == 'Prod':
            for rule in security_group['IpPermissions']:
                # Check if the rule is for any of the known ports
                from_port = str(rule.get('FromPort', ''))
                to_port = str(rule.get('ToPort', ''))
                
                if from_port in known_ports or to_port in known_ports:
                    # Check the IP ranges for specified IPs
                    for ip_range in rule.get('IpRanges', []):
                        if ip_range.get('CidrIp') in ['172.31.90.192/32', '54.146.70.175/32', '172.31.0.0/16']:
                            port = from_port if from_port in known_ports else to_port
                            prod_violation_message = f"Account: {account_name} - SG ID: {security_group['GroupId']} - Port: {port} - IP: {ip_range.get('CidrIp')}"
                            prod_violations.append(prod_violation_message)


def send_to_google_chat(webhook_url, message_body):
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        'text': message_body
    }
    response = requests.post(webhook_url, headers=headers, json=data)
    return response.status_code, response.text


def exportCredentials(account):
    session = boto3.Session(profile_name="jenkins")
    sts = session.client("sts")
    response = sts.assume_role(RoleArn=f"arn:aws:iam::{list(account.values())[0]}:role/RoleForRootAccount",RoleSessionName=f"{list(account.keys())[0]}")
    return response['Credentials']

###############################
               
known_ports = ["22", "2228", "3389", "8965", "5432", "7854", "1521", "7527", "3306", "4307", "6379", "27017", "1-65535"]
violations = []
prod_violations = []

def process_account(account):
    credentials = exportCredentials(account)
    account_name = list(account.keys())[0]
    get_security_group_details(credentials, account_name)

with ThreadPoolExecutor(max_workers=10) as executor:
    future_to_account = {executor.submit(process_account, account): account for account in awsAccounts}
    for future in as_completed(future_to_account):
        account = future_to_account[future]
        try:
            future.result()
        except Exception as exc:
            print('%r generated an exception: %s' % (account, exc))

def format_google_chat_message(header, violations):
    
    formatted_message = f"{header}\n\n"
    
    # Add each violation as a bullet point
    for violation in violations:
        # Remove unnecessary HTML tags from the violation message
        clean_violation = violation.replace("<br>", "").strip()
        formatted_message += f"- {clean_violation}\n"
    
    formatted_message += "\nKindly remove the access from respective security groups. Thank you!"
    
    return formatted_message

# Google Chat Webhook URL
google_chat_webhook_url = 'https://chat.googleapis.com/v1/spaces/AAAAVm58MNw/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=lavdyE8b_okfmb8KKAl_dwWHN424IvA-OkM9o9QvRh4'

# For Public Access
if violations:
    header = "*ALERT: Public Access in AWS Security Groups*"
    formatted_message = format_google_chat_message(header, violations)
    # Send the message to Google Chat
    status_code, response_text = send_to_google_chat(google_chat_webhook_url, formatted_message)

# For VPN access in Prod Env
if prod_violations:
    header = "*ALERT: VPN Access in AWS Security Groups - Prod Environment*"
    formatted_message = format_google_chat_message(header, prod_violations)
    # Send the message to Google Chat
    status_code, response_text = send_to_google_chat(google_chat_webhook_url, formatted_message)
