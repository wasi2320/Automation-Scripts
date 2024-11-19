import boto3

def exportCredentials(account):
  session = boto3.Session(profile_name="jenkins")
  sts = session.client("sts")
  response = sts.assume_role(RoleArn=f"arn:aws:iam::{list(account.values())[0]}:role/RoleForRootAccount",RoleSessionName=f"{list(account.keys())[0]}")
  return response['Credentials']

def get_standards_status(credentials, region, accountId):
    """
    Fetches security findings from AWS Security Hub for the given account and region.
    Filters findings based on active status and non-suppressed workflow.
    Uses the ARNs of enabled standards to filter findings in code.

    Parameters:
    - credentials (dict): AWS credentials.
    - region (str): The AWS region.
    - accountId (str): The account ID.

    Returns:
    - dict: standardsDict with finding details.
    """
    # Create Security Hub client
    securityhub = boto3.client(
        'securityhub',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )

    # Retrieve enabled standards
    enabled_standards_response = securityhub.get_enabled_standards()
    enabled_standards = enabled_standards_response.get('StandardsSubscriptions', [])

    # Store the ARNs of enabled standards in a set for easy filtering
    enabled_standards_arns = set(standard['StandardsSubscriptionArn'] for standard in enabled_standards)

    # Initialize standards dictionary
    standardsDict = {}

    # Set up filters for findings
    filters = {
        'AwsAccountId': [{'Value': accountId, 'Comparison': 'EQUALS'}],
        'ProductName': [{'Value': 'Security Hub', 'Comparison': 'EQUALS'}],
        'RecordState': [{'Value': 'ACTIVE', 'Comparison': 'EQUALS'}]
    }

    # Retrieve findings using pagination
    findings_paginator = securityhub.get_paginator('get_findings')
    pages = findings_paginator.paginate(Filters=filters, MaxResults=100)

    for page in pages:
        for finding in page.get('Findings', []):
            # Filter findings based on enabled standards ARNs
            prodFields = finding.get('ProductFields', {})
            standardsArn = prodFields.get('StandardsArn') or prodFields.get('StandardsGuideArn')

            # Check if finding is related to an enabled standard
            if standardsArn and standardsArn in enabled_standards_arns:
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

def extractSecurityHubScore(credentials, account):
    """
    Extracts AWS Security Hub score for the given account.

    Parameters:
    - credentials (dict): AWS credentials.
    - account (str): Account name.

    Returns:
    - dict: Dictionary containing compliance scores for each standard.
    """
    # Define region based on account
    region = "us-east-2" if account == "Glaukos" else "us-east-1"

    # Retrieve account ID based on account name (you may need to adjust this mapping according to your data)
    account_mapping = {
        "Fluke": "764199743830",
        "client": "account_id",
        "Glaukos":"161503510311"
    }
    accountId = account_mapping.get(account)

    if accountId is None:
        print(f"Account ID for {account} not found.")
        return None

    # Get standards status
    standardsDict = get_standards_status(credentials, region, accountId)

    # Calculate compliance scores
    compliance_scores = generateScore(standardsDict)

    # Return compliance scores for each standard
    return compliance_scores

# Main function that uses the above functions
awsAccounts = [{"Fluke":"764199743830"},{"client":"account_id"},{"Glaukos":"161503510311"}]
details = {}

for account in awsAccounts:
    credentials = exportCredentials(account)
    result = extractSecurityHubScore(credentials, list(account.keys())[0])
    print(f"Compliance scores for account {list(account.keys())[0]}:")
    # Iterate through each standard and its associated score in the result dictionary
    for standard, score_dict in result.items():
        # Extract the score from the score dictionary and print it
        score = score_dict["Score"]
        print(f"Standard: {standard}, Score: {score:.2f}%")


# def exportCredentials(account):
#   session = boto3.Session(profile_name="jenkins")
#   sts = session.client("sts")
#   response = sts.assume_role(RoleArn=f"arn:aws:iam::{list(account.values())[0]}:role/RoleForRootAccount",RoleSessionName=f"{list(account.keys())[0]}")
#   return response['Credentials']

# ############################################# Write Data to Sheet #########################################
# awsAccounts = [{"Fluke":"764199743830"},{"client":"account_id"}]
# details = {}

# for account in awsAccounts:
#   credentials = exportCredentials(account)
#   result = extractSecurityHubScore(credentials, list(account.keys())[0])
#   print(result)