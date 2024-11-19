import subprocess
import json
import boto3


def sendEmail(email,subject,FinalmsgBody):
    session = boto3.Session(profile_name="jenkins")    
    ses_client = session.client('ses')
    response = ses_client.send_email(
        Source='no-reply@email@email.com',
        Destination={
            #'ToAddresses': ["umair.ahmad@email@email.com"],
            'ToAddresses': [email],
            'CcAddresses': ['securityhub-alarms@email@email.com'],
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
    subject = 'Imp - Linode Resources Followup'
    for email in assembledDetails.keys():
        serverDetails = assembledDetails[email]
        #print(email)
        #print("\n")
        #print(serverDetails)
        #print("\n\n") 
        msgBody = ''
        for serverDetail in serverDetails:
            serverDetail = ''.join(serverDetail)
            msgBody = msgBody + f'<tr> <td>{serverDetail}</td> </tr>'
        FinalmsgBody = f'<head><style>table, td {{ border: 1px solid #333; }} thead, tfoot {{ background-color: #333; color: #fff; }} </style></head><body><p>Hello Team,<br>Hope you all are doing great,<br>In this weekly follow-up, we are sharing the linode servers details which are, according to our knowledge, owned/requested by your team. Please go through the following list and check if there is any server that is not required anymore or any server which should not be in your teams ownership then please inform the devops team immediately. So we can get rid of dangling and unwanted servers from our infrastructure. Devops Team will do followup with you every friday to review this email with you as well. Invite has been already shared with your team. <br> We highly appreciate your co-operation.<br><table><thead> <tr>  <th>Servers Details</th> </tr> </thead> {msgBody} </table><br>In case, you need all the above-mentioned servers then you can ignore this mail. <p style="background-color:tomato;">Kindly never share any credentials, keys, or details of resources other than the concerned ones.</p>Best Regards,<br>Devops domain</p></body></html>'
        sendEmail(email,subject,FinalmsgBody)



def ExtractLinodesDetails():
    linodes = subprocess.check_output("linode-cli linodes list --json", shell=True)
    linodes = json.loads(linodes.decode())
    count = 0
    for linode in linodes:
        product , environment ,owner = '', '', ''
        instanceName   = linode['label']
        instanceStatus = linode['status']
        instancePublicIp= linode['ipv4'][0]
        instanceTags = linode['tags']
        for tag in instanceTags:
            if tag in products:
                product = tag
            elif tag in environments:
                environment = tag
            elif tag in owners:
                owner = tag

        if product and environment and owner:
            if owner not in details:
                details[owner] = []
            details[owner].append(f"<b> Name:</b> {instanceName}, <b>Product:</b> {product}, <b>Environment:</b> {environment}, <b>Public IP:</b> {instancePublicIp}, <b>Instance State:</b> {instanceStatus}<br>")
        else:
            tagsNotFoundAlert = f"<body><p>Hi Team,<br> This instance <b>{instanceName}</b> in <b>Linode</b> does not have proper tags. Kindly add mandatory tags with this instance.<br>Thank you </p></body>" 
            sendEmail("agileadmin@email@email.com","Tag Issue - Linode Server",tagsNotFoundAlert)

###################################

details = {}
products = ["AWS-Internal"]
environments = ["Prod", "Dev", "Test", "Demo", "Temp"]
owners = ["engineeringhub-team@email@email.com", "integrationteam@email@email.com", "portalandarchiver-team@email@email.com", "ets-team@email@email.com", "customdev-team@email@email.com", "database-team@email@email.com", "configuration-team@email@email.com", "agileadmin@email@email.com"]

ExtractLinodesDetails()
disperseEmails(details)
