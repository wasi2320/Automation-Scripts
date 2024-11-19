import boto3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Mapping of account names to IDs
aws_account_map = {
    "Unicom": "833087694193",
    "Motorola": "692078465827"
}

def sendEmail(email, subject, FinalmsgBody):
    session = boto3.Session(profile_name="jenkins")
    ses_client = session.client('ses')
    response = ses_client.send_email(
        Source='no-reply@email@email.com',
        Destination={
            'ToAddresses': ["araizrashiq@email@email.com"],
            # 'ToAddresses': [email]  # Uncomment to use dynamic recipient
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

def get_security_group_details(credentials, account_name, product_name, resource_type):
    # Set the region based on account_name
    region = 'us-east-2' if account_name == 'Glaukos' else 'us-east-1'

    # Create a session with the assumed role credentials
    session = boto3.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )
    ec2 = session.client('ec2')
    rds = session.client('rds')  # RDS client to interact with RDS resources
    
    # Define tags for filtering instances based on product name
    tags = {
        'Environment': 'Prod',
        'Team': 'APPS',
        'Product': 'EGNC',
        'Name': product_name
    }
    filters = [{'Name': f'tag:{key}', 'Values': [value]} for key, value in tags.items()]
    
    if resource_type == 'Server':  # If EC2
        # Retrieve EC2 instances based on tags
        instances = ec2.describe_instances(Filters=filters)['Reservations']
        for reservation in instances:
            for instance in reservation['Instances']:
                # Get security groups associated with the instance
                for sg in instance['SecurityGroups']:
                    add_ssh_rule_to_security_group(ec2, sg['GroupId'], '172.31.90.192')  # IP to be allowed
    elif resource_type == 'Database':  # If RDS
        # Retrieve RDS instances based on tags
        db_instances = rds.describe_db_instances()['DBInstances']
        for db_instance in db_instances:
            # Check if the DB instance matches the product name tag
            for tag in db_instance.get('TagList', []):
                if tag['Key'] == 'Name' and tag['Value'] == product_name:
                    # Get security groups associated with the RDS instance
                    for sg in db_instance['VpcSecurityGroups']:
                        add_rds_rule_to_security_group(ec2, sg['VpcSecurityGroupId'], '172.31.90.192')  # IP to be allowed
    else:
        print(f"Unknown resource type: {resource_type}")

def add_ssh_rule_to_security_group(ec2_client, security_group_id, ip):
    # Function to add SSH rule to the security group
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpProtocol='tcp',
            FromPort=22,
            ToPort=22,
            CidrIp=f'{ip}/32'
        )
        print(f"SSH rule added to Security Group {security_group_id}")
    except ec2_client.exceptions.ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print(f"SSH rule already exists for Security Group {security_group_id}")
        else:
            print(f"Error adding SSH rule to Security Group {security_group_id}: {e}")

def add_rds_rule_to_security_group(ec2_client, security_group_id, ip):
    # Function to add rule for RDS (port 5432) to the security group
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpProtocol='tcp',
            FromPort=5432,
            ToPort=5432,
            CidrIp=f'{ip}/32'
        )
        print(f"RDS rule (port 5432) added to Security Group {security_group_id}")
    except ec2_client.exceptions.ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print(f"RDS rule already exists for Security Group {security_group_id}")
        else:
            print(f"Error adding RDS rule (port 5432) to Security Group {security_group_id}: {e}")

def exportCredentials(account_id):
    session = boto3.Session(profile_name="jenkins")
    sts = session.client("sts")
    response = sts.assume_role(
        RoleArn=f"arn:aws:iam::{account_id}:role/RoleForRootAccount",
        RoleSessionName="jenkinsSession"
    )
    return response['Credentials']

def process_account(account_name, product_name, resource_type):
    # Map account name to account ID
    account_id = aws_account_map.get(account_name)
    if not account_id:
        print(f"Account name '{account_name}' not found in account mapping.")
        return

    # Export credentials and process security groups
    credentials = exportCredentials(account_id)
    get_security_group_details(credentials, account_name, product_name, resource_type)

# Main execution
if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 aws-firewall-rule-add.py <product_name> <account_name> <resource_type>")
        sys.exit(1)

    product_name = sys.argv[1]
    account_name = sys.argv[2]
    resource_type = sys.argv[3]  # Either 'Server' (EC2) or 'Database' (RDS)

    # Process accounts concurrently
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_account, account_name, product_name, resource_type)]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"An error occurred: {e}")
