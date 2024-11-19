import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
import time

################################## Authentication #########################

def load_credentials(scopes, subject=None):
    credentials = service_account.Credentials.from_service_account_file(
        'project-birthday-automation-3f7c3bb8ab59.json',
        scopes=scopes,
        subject=subject  # Add subject parameter for impersonation
    )
    return credentials

###########################################################################

SPACE_ID = 'spaces/AAAAN-kvrFo'  # Update your space ID here

##################################### Functions ###########################

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
    
    message_text = f"Belated Happy Birthday, {mentions} 🎊 \n\nMay you have an amazing year that ends with accomplishing all the great goals that you have set!"
    
    message = {
        "text": message_text,
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
    chat_service = build('chat', 'v1', credentials=credentials)

    users = [{
        'PrimaryEmail': 'bobschwartz@email@email.com',
        'birthDate': '26/05',
        'imageUrl': 'https://i.postimg.cc/nc3qy9Jf/Birthday-Post-for-May-2024-14.png',
        'userID': get_user_id_by_email('bobschwartz@email@email.com')
    }]
 
    if users:
        send_birthday_message(chat_service, users, users[0]['imageUrl'])

main()
