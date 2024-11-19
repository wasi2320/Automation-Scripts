from google.oauth2 import service_account
from googleapiclient.discovery import build
import boto3
from config import awsAccounts

def load_credentials():
    credentials = service_account.Credentials.from_service_account_file(
        'project-resources-followup-3ed10b2be421.json',
        scopes=['https://www.googleapis.com/auth/chat.bot']
    )
    return build('chat', 'v1', credentials=credentials)

###########################################################################

def get_gp2_volumes(credentials, account, details):

    region = "us-east-2" if account == "Glaukos" else "us-east-1"
    ec2 = boto3.client('ec2', aws_access_key_id=credentials['AccessKeyId'],
                       aws_secret_access_key=credentials['SecretAccessKey'],
                       aws_session_token=credentials['SessionToken'],
                       region_name=region)  # Adjust region if needed

    # Filter for volumes that are of type 'gp2'
    volumes = ec2.describe_volumes(Filters=[{'Name': 'volume-type', 'Values': ['gp2']}])

    if account not in details:
        details[account] = []

    for volume in volumes['Volumes']:
        volume_id = volume['VolumeId']
        volume_type = volume['VolumeType']
        details[account].append(f"Volume ID: {volume_id}, Type: {volume_type}")

def exportCredentials(account):
    session = boto3.Session(profile_name="jenkins")
    sts = session.client("sts")
    response = sts.assume_role(RoleArn=f"arn:aws:iam::{list(account.values())[0]}:role/RoleForRootAccount",RoleSessionName=f"{list(account.keys())[0]}")
    return response['Credentials']

#####################################################################

def format_message_for_chat(details):
    formatted_message = {
        "cards": [{
            "header": {"title": "AWS Volumes of Type gp2"},
            "sections": []
        }]
    }
    
    for account, volumes in details.items():
        if volumes:  # Skip accounts with empty results
            section = {
                "header": f"<font color=\"#ba0214\">Account: {account}</font>",
                "widgets": [{
                    "textParagraph": {
                        "text": "<br>".join(volumes)
                    }
                }]
            }
            formatted_message["cards"][0]["sections"].append(section)
    
    return formatted_message

#######################################################################
details = {}

def send_message(chat):

    for account in awsAccounts:
        credentials = exportCredentials(account)
        get_gp2_volumes(credentials, list(account.keys())[0], details)
    
    formatted_message = format_message_for_chat(details)  # Use formatted data for message

    # space_id = "spaces/AAAAMD1LdBU"
    space_id = "spaces/AAAAY7kSSYI" #testing

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