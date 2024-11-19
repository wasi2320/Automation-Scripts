import boto3
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

##########################################################################################################

 # Combine the scopes needed for both the Chat and Sheets APIs
combined_scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/chat.bot']

spreadsheet_id = '12KtAKnUOWlBzzETc2aIqnrRAiBxAaYDaLLinnuy9nP8'
start_range='AWS!A1'
sheet_id = '982930438'

def load_credentials(combined_scopes):
    credentials = service_account.Credentials.from_service_account_file(
        'project-resources-followup-3ed10b2be421.json',
        scopes=combined_scopes
    )
    return credentials
        
############################################# Computational Code #########################################

def extractOpenSearchDetails(credentials, account, details):
    region = "us-east-2" if account == "Glaukos" else "us-east-1"
    oSearchResource = boto3.client(
        'opensearch',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )

    domainNameList = oSearchResource.list_domain_names()

    # Convert account to string if it's a dictionary
    if isinstance(account, dict):
        # Using the key of the dictionary as the account name
        account_name = next(iter(account.keys()), 'Unknown')
    else:
        account_name = account

    if domainNameList['DomainNames']:
        for domain in domainNameList['DomainNames']:
            domainName = domain['DomainName']
            
            domainConfig = oSearchResource.describe_domain(DomainName=domainName)
            clusterConfig = domainConfig.get('DomainStatus', {}).get('ClusterConfig', {})
            instanceType = clusterConfig.get('InstanceType', 'Unknown')
            instanceCount = clusterConfig.get('InstanceCount', 'Unknown')

            domainARN = f"arn:aws:es:{region}:{list(account.values())[0]}:domain/{domainName}"
            
            # Get owner and requester tags
            tags = oSearchResource.list_tags(ARN=domainARN)['TagList']

            owner = next((tag['Value'] for tag in tags if tag['Key'] == 'Owner'), 'Unknown')
            requester = next((tag['Value'] for tag in tags if tag['Key'] == 'Requester'), 'Unknown')

            key = f"{account_name}-{domainName}"
            details[key] = {
                'Account': account_name,
                'Name': domainName,
                'Type': 'OpenSearch',
                'Instance Details': f'{instanceType}, Count: {instanceCount}',
                'Owner': owner,
                'Requester': requester
            }

def extractRDSDetails(credentials, account, details):
    region = "us-east-2" if account == "Glaukos" else "us-east-1"
    rds = boto3.client(
        'rds',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )
    
    rdsInstances = rds.describe_db_instances()

    for dbInstance in rdsInstances['DBInstances']:
        dbInstanceName = dbInstance['DBInstanceIdentifier']
        dbInstanceType = dbInstance['DBInstanceClass']
        
        # Get owner and requester tags
        tags = rds.list_tags_for_resource(
            ResourceName=dbInstance['DBInstanceArn']
        )['TagList']
        owner = next((tag['Value'] for tag in tags if tag['Key'] == 'Owner'), 'Unknown')
        requester = next((tag['Value'] for tag in tags if tag['Key'] == 'Requester'), 'Unknown')

        key = f"{account}-{dbInstanceName}"
        details[key] = {
            'Account': account,
            'Name': dbInstanceName,
            'Type': 'RDS',
            'Instance Type': dbInstanceType,
            'Owner': owner,
            'Requester': requester
        }

def extractEC2Details(instances, account, details):
    for instance in instances:
        serverName = next((tag['Value'] for tag in instance.tags if tag['Key'] == 'Name'), instance.id)
        # Get owner and requester tags
        tags = instance.tags
        owner = next((tag['Value'] for tag in tags if tag['Key'] == 'Owner'), 'Unknown')
        requester = next((tag['Value'] for tag in tags if tag['Key'] == 'Requester'), 'Unknown')

        key = f"{account}-{serverName}"
        details[key] = {
            'Account': account,
            'Name': serverName,
            'Type': 'EC2',
            'Instance Type': instance.instance_type,
            'Owner': owner,
            'Requester': requester
        }

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

############################################# Write Data to Sheet #########################################
# Format dictionary for Google Sheets
def format_details_for_sheet(details):
    formatted_data = [["Account", "Name", "Resource", "Type", "Owner", "Requester"]]  # Header row
    for key, value in details.items():
        row = [
            str(value.get('Account', 'Unknown')),
            str(value.get('Name', 'Unknown')),
            str(value.get('Type', 'Unknown')),
            str(value.get('Instance Details', 'Unknown') if value.get('Type') == 'OpenSearch' else value.get('Instance Type', 'Unknown')),
            str(value.get('Owner', 'Unknown')),
            str(value.get('Requester', 'Unknown'))
        ]
        formatted_data.append(row)
    return formatted_data

def write_to_google_sheet(sheets_service, details):
   
    sheet = sheets_service.spreadsheets()
   
    # Format the data for Google Sheets
    formatted_values = format_details_for_sheet(details)

    body = {
        'values': formatted_values
    }

    try:
        sheet.values().update(
            spreadsheetId=spreadsheet_id,
            range=start_range,  # Update as needed
            valueInputOption='RAW',
            body=body
        ).execute()
        print("Data written to Google Sheet successfully.")

    except Exception as e:
        print(f"Failed to write data to Google Sheet. Error: {e}")

credentials = load_credentials(combined_scopes)
sheets_service = build('sheets', 'v4', credentials=credentials)
awsAccounts = [{"AMVAC":"076418772025"},{"Audit":"636565144251"},{"Boxabl":"663597579657"},{"ChristieDigital":"839212731255"},{"Coast":"353207067385"},{"Demodomain":"901455619825"},{"Fluke":"764199743830"},{"Glaukos":"161503510311"},{"LogArchive":"822500291637"},{"Logitech":"361461582704"},{"Motorola":"692078465827"},{"NJOY":"170749925590"},{"PureStorage":"796227435910"},{"Roche":"659912718911"},{"RollandHill":"953909861079"},{"SallyBeauty":"076228895121"},{"SambaNova":"062059234629"},{"TDK":"832512569477"},{"Unicom":"833087694193"},{"Vpccontrol":"222829612732"},{"client":"account_id"},{"Nissha":"514598057510"},{"domain":"101380220521"}]
details = {}

for account in awsAccounts:
    credentials = exportCredentials(account)
    instances = getInstances(credentials,account)
    extractEC2Details(instances,list(account.keys())[0],details)
    extractRDSDetails(credentials,list(account.keys())[0],details)
    extractOpenSearchDetails(credentials,account,details)

write_to_google_sheet(sheets_service, details)
