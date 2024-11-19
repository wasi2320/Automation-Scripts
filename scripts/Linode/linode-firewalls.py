import subprocess
import json
import boto3

def sendEmail(email,subject,FinalmsgBody):
    session = boto3.Session(profile_name="jenkins")    
    ses_client = session.client('ses')
    response = ses_client.send_email(
        Source='no-reply@email@email.com',
        Destination={
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


def ExtractLinodesFirewalls():
  firewalls = subprocess.check_output("linode-cli firewalls list --json", shell=True)
  firewalls = json.loads(firewalls.decode())
  for firewall in firewalls:
    inboundRules = firewall['rules']['inbound']
    for inboundRule in inboundRules:
      ports=(inboundRule['ports'].replace(" ","")).split(",")
      addresses=inboundRule['addresses']['ipv4']
      if set(knownPorts).intersection(ports) and '0.0.0.0/0' in addresses :
        #print(firewall['label'],ports, addresses)
        violations.append(f"<br>{firewall['label']}")

#knownPorts = ["SSH","RDP","POSTGRES","ORACLE","MYSQL","REDIS","MONGODB","ALL PORTS"]
knownPorts = ["22","3389","5432","1521","3306","6379","27017","1-65535"]
violations = []

ExtractLinodesFirewalls()
if violations:
  msgBody = f"<body><p>Hi Team,<br>There is public access granted against high-risk ports(22,3389,5432,1521,3306,6379,27017,1-65535) in following firewalls of linode: <br> {violations} <br>Kindly remove public access from respective firewalls.<br>Thank you </p></body>"
  sendEmail('agileadmin@email@email.com','Action Required: Public Access in Linode Firewalls', msgBody)

