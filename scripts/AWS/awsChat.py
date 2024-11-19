import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
import boto3
from config import awsAccounts

def load_credentials():
    credentials = service_account.Credentials.from_service_account_file(
        'project-resources-followup-3ed1sda0b2be421.json',
        scopes=['https://www.googleapis.com/auth/chats.bot']
    )
    return build('chat', 'v1', credentials=credentials)

###########################################################################

def extractEC2Details(instances,account,details):
    tagsNotFound = []
    team, product,environment, ownerEmail = '', '', '', ''
    for instance in instances:
        try:
            # Check if the instance state is not 'stopped'
            if instance.state['Name'] == 'stopped':
                continue

            skip_instance = False

            for tag in instance.tags:
                if tag['Key'] == 'Name':
                    serverName = tag['Value']
                if tag['Key'] == 'Product':
                    product = tag['Value']
                if tag['Key'] == 'Team':
                    team = tag['Value']
                if tag['Key'] == 'Owner':
                    ownerEmail = tag['Value']
                if tag['Key'] == 'Requester':
                    requester = tag['Value']
                if tag['Key'] == 'Environment':
                    environment = tag['Value']
                    if environment.lower() == 'prod':
                        skip_instance = True
                        break  # Skip instances with 'Environment' set to 'Prod'

            if skip_instance:
                continue

            if product and team and environment and ownerEmail:
                if ownerEmail not in details:
                    details[ownerEmail] = {account:[]}
                if account not in details[ownerEmail]:
                    details[ownerEmail][account] = []
                # details[ownerEmail][account].append(f"(EC2) Name: {serverName},Product: {product},Type: {instance.instance_type},Environment: {environment},Public IP: {instance.public_ip_address},Private IP: {instance.private_ip_address},Instance State: {instance.state['Name']}")
                details[ownerEmail][account].append(f"*IP:* {instance.private_ip_address}, *Product:* {product}, *Env:* {environment}, *Status:* {instance.state['Name']}, *Requester:* {requester}")
            else:
                tagsNotFound.append(f'<br><b>Account:</b> {account} <b>EC2:</b> {instance.id}')
        except Exception as  ex:
            tagsNotFound.append(f'<br><b>Account:</b> {account} <b>EC2:</b> {instance.id}')

def getInstances(credentials,account):
    if list(account.keys())[0] == "Glaukos":
        ec2 = boto3.resource('ec2',aws_access_key_id=credentials['AccessKeyId'],aws_secret_access_key=credentials['SecretAccessKey'],aws_session_token=credentials['SessionToken'],region_name="us-east-2")
        response = ec2.instances.all()
        return response
    else:    
        ec2 = boto3.resource('ec2',aws_access_key_id=credentials['AccessKeyId'],aws_secret_access_key=credentials['SecretAccessKey'],aws_session_token=credentials['SessionToken'],region_name="us-east-1")
        response = ec2.instances.all()
        return response

def exportCredentials(account):
    session = boto3.Session(profile_name="jenkins")
    sts = session.client("sts")
    response = sts.assume_role(RoleArn=f"arn:aws:iam::{list(account.values())[0]}:role/RoleForRootAccount",RoleSessionName=f"{list(account.keys())[0]}")
    return response['Credentials']

############################################################

def format_aws_data(aws_data):
    # Initialize a list to store formatted messages for each account
    formatted_messages = []

    # Iterate through AWS data and format it into messages
    for team, accounts in aws_data.items():
        for account, instances in accounts.items():
            account_message = f"*Account:* {account}\n"
            instance_messages = []

            for instance_info in instances:
                instance_messages.append(f"- {instance_info}")

            account_message += "\n".join(instance_messages)
            formatted_messages.append(account_message)

    # Create a single message combining all account messages
    full_message = "\n\n".join(formatted_messages)

    return full_message

##############################################################

internalSupport = 'spaces/AAAAyFtYoMA'
customdev = 'spaces/AAAAvBFRzy8'
etsAndArchiver = 'spaces/AAAAdAJ6fvU'
ecvteam = 'spaces/AAAA3MgClXc'
egncteam = 'spaces/AAAA-POgb60'
integration = 'spaces/AAAAKqZGKn4'
configteam = 'spaces/AAAARqxadTU'

#Team Leads
ahsanali = "<users/117931362193714532964>"
zarakasim = "<users/109390037178208850279>"
allteam = "<users/all>" # add this as a lead where Lead is not available.

customdevLead = "<users/114816286890948404413>"         # Momin Siddiqui
etsAndArchiverLead = "<users/100978000411196146309>"    # Majid Zulfiqar
ecvLead = "<users/100978000411196146309>"               # Majid Zulfiqar
egncLead = "<users/116466419247931773920>"              # Umaid Haider
integrationLead = "<users/102597798093751269620>"       # Absaar Javed
configLead = "<users/106982274625285022286>"            # Ijaz ul Hassan

############### Teams vis message send ####################
# Define a dictionary to map teams to SPACE_IDs and Team Leads
team_to_space = {
    'database-team@email@email.com': {'space_id': internalSupport, 'lead': allteam},
    'customdev-team@email@email.com': {'space_id': customdev, 'lead': customdevLead},
    'portalandarchiver-team@email@email.com': {'space_id': etsAndArchiver, 'lead': etsAndArchiverLead},
    'ets-team@email@email.com': {'space_id': etsAndArchiver, 'lead': etsAndArchiverLead}, # Same space as portalandarchiver-team
    'engineeringhub-team@email@email.com': {'space_id': ecvteam, 'lead': ecvLead},
    'egncteam@email@email.com': {'space_id': egncteam, 'lead': egncLead},
    'integrationteam@email@email.com': {'space_id': integration, 'lead': integrationLead},
    'configuration-team@email@email.com': {'space_id': configteam, 'lead': configLead},
    # Add more team to SPACE_ID mappings as needed
    }

def send_message(chat):

    details = {}

    for account in awsAccounts:
        credentials = exportCredentials(account)
        instances = getInstances(credentials, account)
        extractEC2Details(instances, list(account.keys())[0], details)

    # Combine resources for portalandarchiver-team and ets-team
    combined_data = {
        'portalandarchiver-team@email@email.com': details.get('portalandarchiver-team@email@email.com', {}),
        'ets-team@email@email.com': details.get('ets-team@email@email.com', {}),
    }
    combined_message = format_aws_data(combined_data)

    # Identify unique space IDs to avoid duplicate messages
    unique_space_ids = set(team_info['space_id'] for team_info in team_to_space.values())

    # Iterate through AWS data and send messages to unique spaces
    for space_id in unique_space_ids:
        teams_for_space = [team for team, team_info in team_to_space.items() if team_info['space_id'] == space_id]

        # Combine messages for teams sharing the same space
        if any(team in ['portalandarchiver-team@email@email.com', 'ets-team@email@email.com'] for team in teams_for_space):
            formatted_message = combined_message
        else:
            formatted_message = format_aws_data({team: details.get(team, {}) for team in teams_for_space})

        # Use the first team in the list to get the team_lead
        team_lead = team_to_space[teams_for_space[0]]['lead']

        message = {
            "text": f"Hello Team and {team_lead}, \n\nPlease review the following resources and consider stopping your instances over the weekend or during off hours!\n\n{formatted_message}\n\nCC: {ahsanali}, {zarakasim}",
        }

        try:
            response = chat.spaces().messages().create(
                parent=space_id,
                body=message
            ).execute()
            print(f"Message sent:", response['name'])

        except Exception as e:
            print(f"Failed to send message. Error: {e}")

##############################################################################
def main():
    chat = load_credentials()
    send_message(chat)

main()

