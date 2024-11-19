import boto3
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
from config import awsAccounts

###########################################################################
 # Combine the scopes needed for both the Chat and Sheets APIs
combined_scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/chat.bot']

spreadsheet_id = '12KtAKnUOWlBzzETc2aIqnrRAiBxAaYDaLLinnuy9nP8'
sheet_name = 'CurrentMonthCost'
current_date = datetime.now().strftime('%b %d')

def load_credentials(combined_scopes):
    credentials = service_account.Credentials.from_service_account_file(
        'project-resources-followup-3ed10b2be421.json',
        scopes=combined_scopes
    )
    return credentials
        
############################################# Computational Code #########################################

def getAWSCostDetails(credentials, account_name, details):
    session = boto3.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )
    
    ce = session.client('ce', 'us-east-1')

    # Dates for the current month
    start_date_current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_date_current_month = start_date_current_month + relativedelta(months=1, days=-1)

    # Get cost and usage data for current month
    current_month_response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': start_date_current_month.strftime('%Y-%m-%d'),
            'End': end_date_current_month.strftime('%Y-%m-%d')
        },
        Granularity='MONTHLY',  # Changed from 'MONTHLY' to 'DAILY'
        Metrics=['UnblendedCost']
    )

    #current_month_cost = current_month_response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount']

    current_month_cost = round(float(current_month_response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount']), 2)
  
    details.setdefault(account_name, {}).setdefault('Cost', []).append({
        'CurrentMonthCost': current_month_cost,
    })

def exportCredentials(account):
    session = boto3.Session(profile_name="jenkins")
    sts = session.client("sts")
    response = sts.assume_role(RoleArn=f"arn:aws:iam::{list(account.values())[0]}:role/RoleForRootAccount",RoleSessionName=f"{list(account.keys())[0]}")
    return response['Credentials']

############################################# Write to Google Sheet Code #########################################
def find_last_and_next_available_column(sheets_service, spreadsheet_id, sheet_name):
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=sheet_name,
        majorDimension='COLUMNS'
    ).execute()
    values = result.get('values', [])

    last_filled_column = None
    next_available_column = None

    def column_label(index):
        """Convert a zero-indexed column number to a column label."""
        label = ''
        while index >= 0:
            index, remainder = divmod(index, 26)
            label = chr(65 + remainder) + label
            index -= 1
        return label

    for col_idx, col in enumerate(values):
        if col and any(cell.strip() != '' for cell in col):
            last_filled_column = column_label(col_idx)
        else:
            next_available_column = column_label(col_idx)
            break

    if not next_available_column:
        next_available_column = column_label(len(values))

    return last_filled_column, next_available_column

# def find_last_and_next_available_column(sheets_service, spreadsheet_id, sheet_name):
#     result = sheets_service.spreadsheets().values().get(
#         spreadsheetId=spreadsheet_id,
#         range=sheet_name,
#         majorDimension='COLUMNS'
#     ).execute()
#     values = result.get('values', [])

#     last_filled_column = None
#     next_available_column = None

#     for col_idx, col in enumerate(values):
#         if col and any(cell.strip() != '' for cell in col):
#             last_filled_column = chr(65 + col_idx)
#         else:
#             next_available_column = chr(65 + col_idx)
#             break

#     if not next_available_column:
#         next_available_column = chr(65 + len(values))

#     return last_filled_column, next_available_column

# def fetch_previous_costs(sheets_service, spreadsheet_id, sheet_name, last_filled_column):
#     if not last_filled_column:
#         return {}
#     range = f"{sheet_name}!{last_filled_column}2:{last_filled_column}"
#     result = sheets_service.spreadsheets().values().get(
#         spreadsheetId=spreadsheet_id,
#         range=range,
#         majorDimension='COLUMNS'
#     ).execute()
#     values = result.get('values', [])[0]
#     return {i + 2: float(value) for i, value in enumerate(values) if value}

def fetch_previous_costs(sheets_service, spreadsheet_id, sheet_name, last_filled_column):
    if not last_filled_column:
        return {}
    range = f"{sheet_name}!{last_filled_column}2:{last_filled_column}"
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range,
        majorDimension='COLUMNS'
    ).execute()
    values = result.get('values', [])[0]
    
    # Extract the numeric part of the string before the dash ' -- '
    cost_dict = {}
    for i, value in enumerate(values):
        if value:
            cost_str = value.split(' -- ')[0]  # Assumes cost and percentage increase are separated by ' -- '
            try:
                cost_float = float(cost_str)
                cost_dict[i + 2] = cost_float  # Map row index to cost
            except ValueError:
                print(f"Error: could not convert string to float: '{cost_str}'")
    
    return cost_dict


def calculate_percentage_increase(previous, current):
    if previous is None or previous == 0:
        return "N/A"
    percentage_increase = ((current - previous) / previous) * 100
    return f"{percentage_increase:.2f}%"  # Format to two decimal places and add percent sign


def write_to_google_sheet(sheets_service, details, last_filled_column):
    sheet = sheets_service.spreadsheets()
    _, next_available_column = find_last_and_next_available_column(sheets_service, spreadsheet_id, sheet_name)
    print(f"Current available column: {next_available_column}")

    header = [[f'Cost ({current_date})']]
    header_body = {'values': header}

    sheet.values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!{next_available_column}1",
        valueInputOption='RAW',
        body=header_body
    ).execute()

    account_names_values = [[account_name] for account_name, _ in details.items()]
    account_names_body = {'values': account_names_values}

    try:
        sheet.values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A2:A{len(details)+1}",
            valueInputOption='RAW',
            body=account_names_body
        ).execute()
        print("Account names written to Google Sheet in column A successfully.")
    except Exception as e:
        print(f"Failed to write account names to Google Sheet. Error: {e}")

    previous_costs = fetch_previous_costs(sheets_service, spreadsheet_id, sheet_name, last_filled_column)

    return_percentage = {}
    cost_and_percentage = []
    for row_index, (account_name, account_details) in enumerate(details.items(), start=2):
        current_cost = account_details['Cost'][0]['CurrentMonthCost']
        previous_cost = previous_costs.get(row_index)
   
        percentage = calculate_percentage_increase(previous_cost, current_cost) if previous_cost is not None else "N/A"
        cost_and_percentage.append([f"{current_cost} -- Increase: +{percentage if percentage != 'N/A' else 'N/A'}"])
        return_percentage[account_name] = f"{percentage}" if percentage != 'N/A' else "N/A"

    cost_values_body = {'values': cost_and_percentage}

    try:
        sheet.values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!{next_available_column}2:{next_available_column}{len(details)+1}",
            valueInputOption='RAW',
            body=cost_values_body
        ).execute()
        print("Data written to Google Sheet successfully.")
    except Exception as e:
        print(f"Failed to write data to Google Sheet. Error: {e}")

    return return_percentage

###########################################################################################################################

def format_aws_data(details, return_percentage):
    formatted_data = []
    for account_name, account_details in details.items():
        cost_details = account_details['Cost'][0]
        billing_period_cost = float(cost_details['CurrentMonthCost'])
        percentage_increase = return_percentage.get(account_name, "N/A")  # Properly handle dictionary
        formatted_data.append(f"Account: {account_name} - ${billing_period_cost:.2f} -- Increase: +{percentage_increase}")
    return '\n'.join(formatted_data)


def get_data(sheets_service, chat_service):
    
    details = {}

    for account in awsAccounts:
        credentials = exportCredentials(account)
        account_name = list(account.keys())[0]
        getAWSCostDetails(credentials, account_name, details)

    last_filled_column, _ = find_last_and_next_available_column(sheets_service, spreadsheet_id, sheet_name)

    try:
        return_percentage = write_to_google_sheet(sheets_service, details, last_filled_column)
    except Exception as e:
        print(f"Failed to send message or write to Google Sheet. Error: {e}")

    formatted_message = format_aws_data(details, return_percentage)

    sheet_link = "https://docs.google.com/spreadsheets/d/12KtAKnUOWlBzzETc2aIqnrRAiBxAaYDaLLinnuy9nP8/edit#gid=982930438"
    dashboard_link = "https://grafana.email@email.com/d/e41ea3e1-0978-4c9e-bfd9-3eca2b2ffacd/aws-billing-dashboard?from=1708113062206&to=1708113362206&orgId=1"

    message = {
    "cards": [
        {
            "header": {
                "title": "AWS Cost Updates",
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
        {
            "sections": [
                {
                    "widgets": [
                        {
                            "textParagraph": {
                                "text": "Check Overview Here",
                            },
                        },
                        {
                            "buttons": [
                                {
                                    "textButton": {
                                        "text": "Open Sheet",
                                        "onClick": {
                                            "openLink": {
                                                "url": sheet_link,
                                            },
                                        },
                                    },
                                },
                                {
                                    "textButton": {
                                        "text": "Open Dashboard",
                                        "onClick": {
                                            "openLink": {
                                                "url": dashboard_link,
                                                },
                                            },
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
        ],
    }

    # space_id = "spaces/AAAAY7kSSYI" #testing space
    space_id = "spaces/AAAA1ntF__4"

    try:
        response = chat_service.spaces().messages().create(
            parent=space_id,
            body=message
        ).execute()
        print(f"Message sent:", response['name'])

    except Exception as e:
        print(f"Failed to send message. Error: {e}")

##############################################################################
def main():

    credentials = load_credentials(combined_scopes)
    # Build the service objects

    sheets_service = build('sheets', 'v4', credentials=credentials)
    chat_service = build('chat', 'v1', credentials=credentials)

    get_data(sheets_service, chat_service)

main()
