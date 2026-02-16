"""
Google Drive OAuth Helper - Generate token locally
Run this on your Windows machine to generate the token file
"""

import os
import json
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/drive']

def main():
    creds = None
    token_path = 'oauth_token.pickle'
    
    # Load credentials
    with open('oauth_credentials.json', 'r') as f:
        client_config = json.load(f)
    
    print("Starting OAuth flow...")
    print("Browser will open. Please authorize the application.\n")
    
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=3000)
    
    # Save token
    with open(token_path, 'wb') as token:
        pickle.dump(creds, token)
    
    print(f"\n✅ Token saved to: {token_path}")
    print("Upload this file to the server at: ad-scout/config/oauth_token.pickle")
    
    # Test
    from googleapiclient.discovery import build
    service = build('drive', 'v3', credentials=creds)
    about = service.about().get(fields='user').execute()
    print(f"Authenticated as: {about['user']['emailAddress']}")

if __name__ == "__main__":
    main()
