import boto3
import logging
from config import awsAccounts

def sendEmail(email,subject,FinalmsgBody):
    session = boto3.Session(profile_name="jenkins")    
    ses_client = session.client('ses')
    response = ses_client.send_email(
        Source='email@email.com',
        Destination={
            #'ToAddresses': ["@email@email.com"],
            'ToAddresses': [email],
            'CcAddresses': ['alarms@email@email.com'],
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

def disperseEmails(assembledDetails):
    subject = 'Imp - AWS Resources Followup'
    for email in assembledDetails.keys():
        serverDetails = assembledDetails[email]
        msgBody = ''
        for account, serverDetail in serverDetails.items():
            serverDetail = ' '.join(serverDetail)
            msgBody = msgBody + f'<tr> <td>{account}</td> <td>{serverDetail}</td> </tr>'
        FinalmsgBody = f'<head><style>table, td {{ border: 1px solid #333; }} thead, tfoot {{ background-color: #333; color: #fff; }} </style></head><body><p>Hello Team,<br>Hope you all are doing great,<br>In this weekly follow-up, we are sharing the AWS resources details which are, according to our knowledge, owned/requested by your team. Please go through the following list and check if there is any resource that is not required anymore or any resource which should not be in your teams ownership then please inform the devops team immediately. So we can get rid of dangling and unwanted resources from our infrastructure. Devops Team will do followup with you every friday to review this email with you as well. Invite has been already shared with your team. <br> We highly appreciate your co-operation.<br><table><thead> <tr> <th>Accounts</th> <th>Resources Details</th> </tr> </thead> {msgBody} </table><br>In case, you need all the above-mentioned resources then you can ignore this mail. <p style="background-color:tomato;">Kindly never share any credentials, keys, or details of resources other than the concerned ones.</p>Best Regards,<br>Devops domain</p></body></html>'
        sendEmail(email,subject,FinalmsgBody)

def extractOpenSearchDetails(credentials,account,details):
    oSearchResourse = boto3.client('opensearch',aws_access_key_id=credentials['AccessKeyId'],aws_secret_access_key=credentials['SecretAccessKey'],aws_session_token=credentials['SessionToken'])
    domainNameList = oSearchResourse.list_domain_names()
    if domainNameList['DomainNames']:
        for domain in domainNameList['DomainNames']:
            accountName = list(account.keys())[0]
            domainName = domain['DomainName']
            domainARN = f"arn:aws:es:us-east-1:{list(account.values())[0]}:domain/{domainName}"
            domainTagsList = oSearchResourse.list_tags(ARN=domainARN)
            team, product, environment, ownerEmail = '', '', '', ''
            for tag in domainTagsList['TagList']:
                if tag['Key'] == 'Product':
                    product = tag['Value']
                if tag['Key'] == 'Team':
                    team = tag['Value']
                if tag['Key'] == 'Environment':
                    environment = tag['Value']
                if tag['Key'] == 'Owner':
                    ownerEmail = tag['Value']
    
            if product and team and environment and ownerEmail:
                if ownerEmail not in details:
                    details[ownerEmail] = {accountName:[]}
                if accountName not in details[ownerEmail]:
                    details[ownerEmail][accountName] = []
                details[ownerEmail][accountName].append(f"<b>(OpenSearch) Name:</b> {domainName}, <b>Product:</b> {product}, <b>Environment:</b> {environment}<br>")
            else:
                tagsNotFound.append(f'<br><b>Account:</b> {accountName} <b>OpenSearch:</b> {domainName}')

def extractS3Details(credentials,account,details):
    s3Resourse = boto3.resource('s3',aws_access_key_id=credentials['AccessKeyId'],aws_secret_access_key=credentials['SecretAccessKey'],aws_session_token=credentials['SessionToken'])
    s3Client = boto3.client('s3',aws_access_key_id=credentials['AccessKeyId'],aws_secret_access_key=credentials['SecretAccessKey'],aws_session_token=credentials['SessionToken'])
    for bucket in s3Resourse.buckets.all():
        try:
            bucketName = bucket.name
            bucketTags = s3Client.get_bucket_tagging(Bucket=bucketName)
            team, product, environment, ownerEmail = '', '', '', ''
            for tag in bucketTags["TagSet"]:
                if tag['Key'] == 'Product':
                    product = tag['Value']
                if tag['Key'] == 'Team':
                    team = tag['Value']
                if tag['Key'] == 'Environment':
                    environment = tag['Value']
                if tag['Key'] == 'Owner':
                    ownerEmail = tag['Value']
    
            if product and team and environment and ownerEmail:
                if ownerEmail not in details:
                    details[ownerEmail] = {account:[]}
                if account not in details[ownerEmail]:
                    details[ownerEmail][account] = []
                details[ownerEmail][account].append(f"<b>(S3) Name:</b> {bucketName}, <b>Product:</b> {product}, <b>Environment:</b> {environment}<br>")
            else:
                tagsNotFound.append(f'<br><b>Account:</b> {account} <b>S3:</b> {bucketName}')
        except:
            tagsNotFound.append(f'<br><b>Account:</b> {account} <b>S3:</b> {bucketName}')

def extractRDSDetails(credentials,account,details):
    if account == "Glaukos":
        rds = boto3.client('rds',aws_access_key_id=credentials['AccessKeyId'],aws_secret_access_key=credentials['SecretAccessKey'],aws_session_token=credentials['SessionToken'],region_name="us-east-2")
        rdsInstances = rds.describe_db_instances()
    else:
        rds = boto3.client('rds',aws_access_key_id=credentials['AccessKeyId'],aws_secret_access_key=credentials['SecretAccessKey'],aws_session_token=credentials['SessionToken'],region_name="us-east-1")
        rdsInstances = rds.describe_db_instances()

    for dbInstance in rdsInstances['DBInstances']:
        dbInstanceName = dbInstance['DBInstanceIdentifier']
        dbInstanceStatus= dbInstance['DBInstanceStatus']
        dbInstanceHost= dbInstance['Endpoint']['Address']
        dbInstanceEngine =  dbInstance['Engine']
        team, product,environment, ownerEmail = '', '', '', ''

        for tag in dbInstance["TagList"]:
            if tag['Key'] == 'Product':
                product = tag['Value']
            if tag['Key'] == 'Team':
                team = tag['Value']
            if tag['Key'] == 'Environment':
                environment = tag['Value']
            if tag['Key'] == 'Owner':
                ownerEmail = tag['Value']

        if product and team and environment and ownerEmail:
            if ownerEmail not in details:
                    details[ownerEmail] = {account:[]}
            if account not in details[ownerEmail]:
                details[ownerEmail][account] = []
            details[ownerEmail][account].append(f"<b>(DB) Name:</b> {dbInstanceName}, <b>Product:</b> {product}, <b>Environment:</b> {environment}, <b>DB Host:</b> {dbInstanceHost},<b>Engine</b> {dbInstanceEngine}  <b>Instance State:</b> {dbInstanceStatus}<br>")
        else:
            tagsNotFound.append(f'<br><b>Account:</b> {account} <b>RDS:</b> {dbInstanceName}')

def extractEC2Details(instances,account,details):
   
    for instance in instances:
        team, product,environment, ownerEmail = '', '', '', ''
        try:
            for tag in instance.tags:
                if tag['Key'] == 'Name':
                    serverName = tag['Value']
                if tag['Key'] == 'Product':
                    product = tag['Value']
                if tag['Key'] == 'Team':
                    team = tag['Value']
                if tag['Key'] == 'Environment':
                    environment = tag['Value']
                if tag['Key'] == 'Owner':
                    ownerEmail = tag['Value']

            if product and team and environment and ownerEmail:
                if ownerEmail not in details:
                    details[ownerEmail] = {account:[]}
                if account not in details[ownerEmail]:
                    details[ownerEmail][account] = []
                details[ownerEmail][account].append(f"<b>(EC2) Name:</b> {serverName}, <b>Product:</b> {product},<b>Type:</b> {instance.instance_type}, <b>Environment:</b> {environment}, <b>Public IP:</b> {instance.public_ip_address},  <b>Private IP:</b> {instance.private_ip_address},  <b>Instance State:</b> {instance.state['Name']}<br>")
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

###############################

details = {}
tagsNotFound = []

for account in awsAccounts:
    credentials = exportCredentials(account)
    instances = getInstances(credentials,account)
    extractEC2Details(instances,list(account.keys())[0],details)
    extractRDSDetails(credentials,list(account.keys())[0],details)
    extractS3Details(credentials,list(account.keys())[0],details)
    extractOpenSearchDetails(credentials,account,details)

disperseEmails(details)

if tagsNotFound:
    tagsNotFoundMsg= f'<body><p>Hi Team,<br>The following resources in the respective accounts do not have appropriate tags(Environment, Owner, Product, Team). {tagsNotFound} <br>Kindly add mandatory tags with these resources.<br>Thank you </p></body>'
    sendEmail('devops@email@email.com','Tags Issue - AWS Resources',tagsNotFoundMsg)
