import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
import boto3
from sc_config import awsAccounts

def load_credentials():
    credentials = service_account.Credentials.from_service_account_file(
        'project-resources-followup-3ed10b2be421.json',
        scopes=['https://www.googleapis.com/auth/chat.bot']
    )
    return build('chat', 'v1', credentials=credentials)

###########################################################################

def get_standards_status(credentials, account_name, accountId):
    """
    Fetches security findings from AWS Security Hub for the given account and region.
    Filters findings based on active status and non-suppressed workflow.
    Constructs a dictionary (standardsDict) to store finding details.

    Parameters:
    - credentials (dict): AWS credentials.
    - region (str): The AWS region.
    - accountId (str): The account ID.

    Returns:
    - dict: standardsDict with finding details.
    """
    # Create Security Hub client
    # Define region based on account
    region = "us-east-2" if account_name == "Glaukos" else "us-east-1"

    securityhub = boto3.client(
        'securityhub',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )

    # Initialize filters for findings
    filters = {
        'AwsAccountId': [{'Value': accountId, 'Comparison': 'EQUALS'}],
        'ProductName': [{'Value': 'Security Hub', 'Comparison': 'EQUALS'}],
        'RecordState': [{'Value': 'ACTIVE', 'Comparison': 'EQUALS'}]
    }

    # Initialize standards dictionary
    standardsDict = {}

    # Retrieve findings using pagination
    findings_paginator = securityhub.get_paginator('get_findings')
    pages = findings_paginator.paginate(Filters=filters, MaxResults=100)

    for page in pages:
        for finding in page.get('Findings', []):
            # Analyze finding and update standardsDict
            build_standards_dict(finding, standardsDict)
    
    return standardsDict

def build_standards_dict(finding, standardsDict):
    """
    Analyzes each Security Hub finding.
    Extracts the control standard and rule ID.
    Updates standardsDict with compliance status for each rule within a standard.

    Parameters:
    - finding (dict): A single Security Hub finding.
    - standardsDict (dict): Dictionary to store finding details.
    """
    # Check if finding has 'Compliance' and 'ProductFields'
    if 'Compliance' in finding and 'ProductFields' in finding:
        status = finding['Compliance']['Status']
        prodField = finding['ProductFields']
        
        # Ignore disabled controls and suppressed findings
        if finding['RecordState'] == 'ACTIVE' and finding['Workflow']['Status'] != 'SUPPRESSED':
            control = None
            rule = None
            
            # Determine control and rule based on AWS or CIS standards
            if 'StandardsArn' in prodField:
                control = prodField['StandardsArn']
                rule = prodField['ControlId']
            elif 'StandardsGuideArn' in prodField:
                control = prodField['StandardsGuideArn']
                rule = prodField['RuleId']
            
            # Process control and rule
            if control is not None:
                # Extract readable control name from ARN, including version information if present
                control_parts = control.split('/')
                controlName = '/'.join(control_parts[1:])

                # Update standardsDict with compliance status
                if controlName not in standardsDict:
                    standardsDict[controlName] = {rule: status}
                elif rule not in standardsDict[controlName] or status == 'FAILED':
                    standardsDict[controlName][rule] = status
    
    return standardsDict

def generateScore(standardsDict):
    """
    Calculates compliance scores for each security standard.
    Scores are based on the percentage of passed rules within a standard.

    Parameters:
    - standardsDict (dict): Dictionary with finding details.

    Returns:
    - dict: resultDict with compliance scores for each standard.
    """
    resultDict = {}

    # Calculate compliance scores for each standard
    for control, rules in standardsDict.items():
        total_controls = len(rules)
        passed_controls = sum(1 for status in rules.values() if status == 'PASSED')

        # Calculate compliance percentage and round it
        if total_controls > 0:
            compliance_percentage = round((passed_controls / total_controls) * 100)
        else:
            compliance_percentage = 0
        
        # Store the score in resultDict
        resultDict[control] = {"Score": compliance_percentage}

    return resultDict

def extractSecurityHubScore(credentials, account_name, accountId):
    """
    Extracts AWS Security Hub score for the given account.

    Parameters:
    - credentials (dict): AWS credentials.
    - account (str): Account name.

    Returns:
    - dict: Dictionary containing compliance scores for each standard.
    """

    # Get standards status
    standardsDict = get_standards_status(credentials, account_name, accountId)

    # Calculate compliance scores
    compliance_scores = generateScore(standardsDict)

    # Return compliance scores for each standard
    return compliance_scores

def exportCredentials(account):
    session = boto3.Session(profile_name="jenkins")
    sts = session.client("sts")
    response = sts.assume_role(RoleArn=f"arn:aws:iam::{list(account.values())[0]}:role/RoleForRootAccount",RoleSessionName=f"{list(account.keys())[0]}")
    return response['Credentials']

############################################################
def calculate_average_score(scores):
    total_score = 0
    count = 0
    for score_info in scores.values():
        total_score += score_info['Score']
        count += 1
    if count == 0:
        return 0
    return int(total_score / count)

def format_aws_data(aws_data):
    formatted_messages = []
    for account_name, scores in aws_data.items():
        avg_score = calculate_average_score(scores)  # Calculate average score
        print(avg_score)

        if avg_score < 100:
            print("Enter in if cond", avg_score)
            message = f"<b>Account:</b> {account_name} - <b>Security Hub Score:</b> <font color=\"#FF0000\">{avg_score}%</font>\n"
        else:
            message = f"<b>Account:</b> {account_name} - <b>Security Hub Score:</b> <font color=\"#00ff00\">{avg_score}%</font>\n"

        formatted_messages.append(message)
    return "".join(formatted_messages)

#For each compliance

# def format_aws_data(aws_data):
#     formatted_messages = []
#     for account_name, scores in aws_data.items():
#         message = f"Account: {account_name}\n"
#         for standard, score in scores.items():
#             message += f"{standard}: Score {score['Score']}%\n"
#         formatted_messages.append(message)

#     return "\n\n".join(formatted_messages)

#####################################################################
details = {}

def send_message(chat):

    for account in awsAccounts:
        account_name, account_id = list(account.items())[0]
        credentials = exportCredentials(account)
        scores = extractSecurityHubScore(credentials, account_name, account_id)
        details[account_name] = scores  # Save scores for each account in details
    
    formatted_message = format_aws_data(details)  # Use formatted data for message

    message = {
    "cards": [
        {
            "header": {
                "title": "AWS Security Hub Scores for Today!",
            },
            "sections": [
                {
                    "widgets": [
                        {
                            "textParagraph": {
                                "text": formatted_message,
                            },
                        },
                    ],
                },
            ],
        },
    ],
    }

    space_id = "spaces/AAAAMD1LdBU"
    #space_id = "spaces/AAAAY7kSSYI" #testing

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

