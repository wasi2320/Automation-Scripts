import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import awsAccounts

def sendEmail(email,subject,FinalmsgBody):
    session = boto3.Session(profile_name="jenkins")    
    ses_client = session.client('ses')
    response = ses_client.send_email(
        Source='no-reply@email@email.com',
        Destination={
            #'ToAddresses': ["@email@email.com"],
            'ToAddresses': [email]
        },
        Message={
            'Subject': {
                'Data': subject,
                'Charset': 'UTF-8'
            },
            'Body': {
                'Html': {
                    'Data': FinalmsgBody,
                    'Charset': 'UTF-8'
                }
            }
        },
    )

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
            if str(rule.get('FromPort', '')) in known_ports or str(rule.get('ToPort', '')) in known_ports:
                # Check the IP ranges for '0.0.0.0/0'
                for ip_range in rule.get('IpRanges', []):
                    if ip_range.get('CidrIp') == '0.0.0.0/0':
                        violations.append(f"<br>Account: {account_name}, Security Group ID: {security_group['GroupId']}")

def check_prod_inbound_rules(security_groups, account_name):
    for security_group in security_groups['SecurityGroups']:
        # Check if the security group has the tag key "Environment" with value "Prod"
        tags = {tag['Key']: tag['Value'] for tag in security_group.get('Tags', [])}
        if tags.get('Environment') == 'Prod':
            for rule in security_group['IpPermissions']:
                # Check if the rule is for any of the known ports
                if str(rule.get('FromPort', '')) in known_ports or str(rule.get('ToPort', '')) in known_ports:
                    # Check the IP ranges for '172.31.90.192/32'
                    for ip_range in rule.get('IpRanges', []):
                        if (ip_range.get('CidrIp') == '172.31.90.192/32' or ip_range.get('CidrIp') == '54.146.70.175/32' or ip_range.get('CidrIp') == '172.31.0.0/16'):
                            prod_violations.append(f"<br>Account: {account_name}, Security Group ID: {security_group['GroupId']}")

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

if violations:
    msgBody = f"<body><p>Hi Team,<br>There is public access granted against high-risk ports (22, 2228, 3389, 8965, 5432, 7854, 1521, 7527, 3306, 4307, 6379, 27017, 1-65535) in following Security Groups of AWS Accounts: <br> {violations} <br><br>Kindly remove public access from respective security groups.<br>Thank you for your attention to this matter!</p></body>"
    # Send the email
    sendEmail('agileadmin@email@email.com','Immediate Action Required: Public Access in AWS Security Groups', msgBody)

if prod_violations:
    prod_msgBody = f"<body><p>Hi Team,<br>There is VPN access granted against high-risk ports (22, 2228, 3389, 8965, 5432, 7854, 1521, 7527, 3306, 4307, 6379, 27017, 1-65535) in following Security Groups within our Production environment: <br> {prod_violations} <br><br>Kindly remove VPN access from respective security groups.<br>Thank you for your attention to this matter!</p></body>"
    # Send the email
    sendEmail('agileadmin@email@email.com','Immediate Action Required: VPN Access in AWS Security Groups - Prod Environment', prod_msgBody)
 
