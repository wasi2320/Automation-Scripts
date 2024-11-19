from google.oauth2 import service_account
from googleapiclient.discovery import build
import boto3
from config import awsAccounts

def load_credentials():
    credentials = service_account.Credentials.from_service_account_file(
        'project-resources-followup-3ed10b2be421.json',
        scopes=['https://www.googleapis.com/auth/chats.bot']
    )
    return build('chat', 'v1', credentials=credentials)

###########################################################################

def get_unattached_volumes(credentials, account, details):
    region = "us-east-2" if account == "Glaukos" else "us-east-1"
    ec2 = boto3.client('ec2', aws_access_key_id=credentials['AccessKeyId'],
                       aws_secret_access_key=credentials['SecretAccessKey'],
                       aws_session_token=credentials['SessionToken'],
                       region_name=region)  # Adjust region if needed

    # Filter for volumes that are available (i.e., unattached)
    volumes = ec2.describe_volumes(Filters=[{'Name': 'status', 'Values': ['available']}])

    if volumes['Volumes']:
        if account not in details:
            details[account] = {'volumes': [], 'elastic_ips': [], 'empty_buckets': []}
        for volume in volumes['Volumes']:
            volume_id = volume['VolumeId']
            volume_name = next((tag['Value'] for tag in volume.get('Tags', []) if tag['Key'] == 'Name'), 'N/A')
            details[account]['volumes'].append(f"Volume ID: {volume_id}, Name: {volume_name}")

def get_unused_elastic_ips(credentials, account, details):
    region = "us-east-2" if account == "Glaukos" else "us-east-1"
    ec2 = boto3.client('ec2', aws_access_key_id=credentials['AccessKeyId'],
                       aws_secret_access_key=credentials['SecretAccessKey'],
                       aws_session_token=credentials['SessionToken'],
                       region_name=region)  # Adjust region if needed

    # Get all Elastic IP addresses
    addresses = ec2.describe_addresses()

    # Filter for addresses that are not associated (AssociationId is null)
    unassociated_addresses = [address for address in addresses['Addresses'] if 'AssociationId' not in address]

    if unassociated_addresses:
        if account not in details:
            details[account] = {'volumes': [], 'elastic_ips': [], 'empty_buckets': []}
        for address in unassociated_addresses:
            allocation_id = address['AllocationId']
            public_ip = address['PublicIp']
            details[account]['elastic_ips'].append(f"Allocation ID: {allocation_id}, Public IP: {public_ip}")

def get_empty_s3_buckets(credentials, account, details):
    region = "us-east-2" if account == "client" else "us-east-1"
    s3 = boto3.client('s3', aws_access_key_id=credentials['AccessKeyId'],
                      aws_secret_access_key=credentials['SecretAccessKey'],
                      aws_session_token=credentials['SessionToken'],
                      region_name=region)  # Adjust region if needed

    buckets = s3.list_buckets()

    empty_buckets = []
    for bucket in buckets['Buckets']:
        bucket_name = bucket['Name']
        objects = s3.list_objects_v2(Bucket=bucket_name)
        if 'Contents' not in objects:
            empty_buckets.append(bucket_name)

    if empty_buckets:
        if account not in details:
            details[account] = {'volumes': [], 'elastic_ips': [], 'empty_buckets': []}
        for bucket_name in empty_buckets:
            details[account]['empty_buckets'].append(f"Bucket Name: {bucket_name}")

def exportCredentials(account):
    session = boto3.Session(profile_name="jenkins")
    sts = session.client("sts")
    response = sts.assume_role(RoleArn=f"arn:aws:iam::{list(account.values())[0]}:role/RoleForRootAccount", RoleSessionName=f"{list(account.keys())[0]}")
    return response['Credentials']

#####################################################################

def format_message_for_chat(details):
    formatted_message = {
        "cards": [{
            "header": {"title": "AWS Toolkit"},
            "sections": []
        }]
    }

    if any(account_details['volumes'] for account_details in details.values()):
        unattached_volumes_section = {
            "header": "<font color=\"#ba0214\">Unattached Volumes</font>",
            "widgets": []
        }
        for account, resources in details.items():
            if resources['volumes']:
                unattached_volumes_section["widgets"].append({
                    "textParagraph": {
                        "text": f"<b>Account: {account}</b><br>" + "<br>".join(resources['volumes'])
                    }
                })
        formatted_message["cards"][0]["sections"].append(unattached_volumes_section)

    if any(account_details['elastic_ips'] for account_details in details.values()):
        unused_elastic_ips_section = {
            "header": "<font color=\"#ba0214\">Un-used Elastic IPs</font>",
            "widgets": []
        }
        for account, resources in details.items():
            if resources['elastic_ips']:
                unused_elastic_ips_section["widgets"].append({
                    "textParagraph": {
                        "text": f"<b>Account: {account}</b><br>" + "<br>".join(resources['elastic_ips'])
                    }
                })
        formatted_message["cards"][0]["sections"].append(unused_elastic_ips_section)

    if any(account_details['empty_buckets'] for account_details in details.values()):
        empty_buckets_section = {
            "header": "<font color=\"#ba0214\">Empty S3 Buckets</font>",
            "widgets": []
        }
        for account, resources in details.items():
            if resources['empty_buckets']:
                empty_buckets_section["widgets"].append({
                    "textParagraph": {
                        "text": f"<b>Account: {account}</b><br>" + "<br>".join(resources['empty_buckets'])
                    }
                })
        formatted_message["cards"][0]["sections"].append(empty_buckets_section)

    return formatted_message

#######################################################################
details = {}

def send_message(chat):
    for account in awsAccounts:
        credentials = exportCredentials(account)
        get_unattached_volumes(credentials, list(account.keys())[0], details)
        get_unused_elastic_ips(credentials, list(account.keys())[0], details)
        get_empty_s3_buckets(credentials, list(account.keys())[0], details)

    formatted_message = format_message_for_chat(details)  # Use formatted data for message

    space_id = "spaces/AAAA1ntF__4"
    # space_id = "spaces/AAAAY7kSSYI"  # testing

    try:
        response = chat.spaces().messages().create(
            parent=space_id,
            body=formatted_message
        ).execute()
        print(f"Message sent:", response['name'])

    except Exception as e:
        print(f"Failed to send message. Error: {e}")

##############################################################################
def main():
    chat = load_credentials()
    send_message(chat)

main()
