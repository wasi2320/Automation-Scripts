import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
import csv
from datetime import datetime, timedelta
import time, random

################################## Authentication #########################

def load_credentials(scopes, subject=None):
    credentials = service_account.Credentials.from_service_account_file(
        'project-birthday-automation-3f7c3bb8ab59.json',
        scopes=scopes,
        subject=subject  # Add subject parameter for impersonation
    )
    return credentials

###########################################################################

SPACE_ID = 'spaces/AAAAN-kvrFo' # Update your space ID here

##################################### Functions ###########################

def get_todays_birthdays(sheet_id, range_name, sheets_service):

    today = datetime.now().strftime('%d/%m')  # Only day and month
    users = []
    
    # Call the Sheets API
    sheet = sheets_service.spreadsheets()
    result = sheet.values().get(spreadsheetId=sheet_id, range=range_name).execute()
    rows = result.get('values', [])

    # Assume the first row is the header
    for row in rows[1:]:  # Skip the header
        # Ensure the row has at least 3 columns (A to C) and birthDate (B column) is not empty
        if len(row) > 2 and row[1]:
            user_data = {
                # Map your columns to the indices, skipping the email (A column)
                'PrimaryEmail': row[0],    # A column
                'birthDate': row[1], # B column
                'imageUrl': row[2]   # C column
            }
            if user_data['birthDate'] == today:
                # Call the function to get user ID by email
                user_data['userID'] = get_user_id_by_email(user_data['PrimaryEmail'])
                users.append(user_data)

    print(users)
    return users

def get_user_id_by_email(target_email):
    """Fetch the Google Chat user ID for a specific user email from Google Directory API."""

    # Impersonate the user with the specified email
    subject = "devops@email@email.com"  # Set the subject to the email address of the user
    combined_scopes = ['https://www.googleapis.com/auth/admin.directory.user.readonly']
    credentials = load_credentials(combined_scopes, subject)
    admin_service = build('admin', 'directory_v1', credentials=credentials)

    try:
        # Retrieve user information using the Admin SDK Directory API
        user = admin_service.users().get(userKey=target_email).execute()
        user_id = user.get('id', '')
        return user_id
    except Exception as e:
        print(f"Error getting user ID: {e}")
        return None

def get_all_space_members(chat_service):
    try:
        # Set up initial conditions for pagination
        page_token = None
        all_members = []
        
        while True:
            # Fetch a page of members
            response = chat_service.spaces().members().list(parent=SPACE_ID, pageToken=page_token).execute()
            
            # Extract member IDs from this page and append to the list
            all_members.extend([member['member']['name'].split('/')[-1] for member in response.get('memberships', [])])
            
            # Check for the next page token
            page_token = response.get('nextPageToken')
            if not page_token:
                # No more pages left
                break

        return all_members
    except Exception as e:
        print(f"Failed to fetch members. Error: {e}")
        return []

def send_birthday_message(chat_service, users, image_url):

    # Check for valid user IDs
    all_space_members = get_all_space_members(chat_service)
    valid_users = [user for user in users if user['userID'] in all_space_members]
    if not valid_users:
        print("No valid users to send a message to.")
        return

    mentions = ' '.join([f"<users/{user['userID']}>" for user in valid_users])
    
    # List of message texts
    messages = [
        f"Happy belated Birthday, {mentions} 🎊 \n\nMay your professional journey be filled with opportunities, growth, and remarkable accomplishments!",
        f"Please join me to wish {mentions} a joyous and fabulous belated birthday🎊 \n\nMay you have a day full of laughter and happiness and a year that brings you much success!",
        f"Please join me to wish {mentions} a joyous and fabulous belated birthday🎊 \n\nWishing you a fantastic year, career growth and success in everything you do!",
        f"Happy belated Birthday, {mentions} 🎊 \n\nMay this year be a stepping stone to even greater accomplishments and success in your career!",
        f"Happy belated Birthday, {mentions} 🎊 \n\nMay your birthday be the start of a year filled with good luck, good health and much happiness!",
        f"Happy belated Birthday, {mentions} 🎊 \n\nHere's to a year of great opportunities, success and career advancement!",
        f"Happy belated Birthday, {mentions} 🎊 \n\nMay you have an amazing year that ends with accomplishing all the great goals that you have set!",
        f"Happy belated Birthday, {mentions} 🎊 \n\nMay this year bring you even more opportunities, personal development, and career success!"
    ]

    # Choose a random message from the list
    chosen_message = random.choice(messages)
    
    message = {
        "text": chosen_message,
        'cards': [{
            'sections': [{
                "widgets": [{
                    "image": {
                        "imageUrl": image_url
                    }
                }]
            }]
        }]
    }

    try:
        response = chat_service.spaces().messages().create(
            parent=SPACE_ID,  
            body=message
        ).execute()

        user_ids = ', '.join([user['userID'] for user in valid_users])
        print(f"Message sent to users {user_ids} with ID:", response['name'])

    except Exception as e:
        print(f"Failed to send message. Error: {e}")

################################### Main Execution ##################################

def main():

    # Combine the scopes needed for both the Chat and Sheets APIs
    combined_scopes = [
        'https://www.googleapis.com/auth/chat.bot',
        'https://www.googleapis.com/auth/spreadsheets.readonly',
        ]
        
    credentials = load_credentials(combined_scopes)
    # Build the service objects
    sheets_service = build('sheets', 'v4', credentials=credentials)
    chat_service = build('chat', 'v1', credentials=credentials)

    sheet_id = '1u5tJpb6jDV-Dv7d02gXq-35tpj6tSzDO9fOgTpm496k'  # Replace with your actual Google Sheet ID
    range_name = 'birthday_automation!A:C'  # Adjust the range as needed
    users = get_todays_birthdays(sheet_id, range_name, sheets_service)
 
    if users:
        # Assuming all users with the same birthday have the same image URL
        send_birthday_message(chat_service, users, users[0]['imageUrl'])

main()
