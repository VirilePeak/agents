"""
Google Drive OAuth - Local Token Generator
Run this on your Windows machine
"""

import os
import json
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/drive']

def main():
    # Load credentials
    with open('oauth_credentials.json', 'r') as f:
        client_config = json.load(f)
    
    print("Starting OAuth flow...")
    print("Browser will open at http://localhost:3000")
    print("Authorize the app, then return here.\n")
    
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=3000)
    
    # Save token
    with open('oauth_token.pickle', 'wb') as token:
        pickle.dump(creds, token)
    
    print(f"\n✅ SUCCESS! Token saved to: oauth_token.pickle")
    print("\nNext step:")
    print("Upload this file to the server at:")
    print("/root/.openclaw/workspace/ad-scout/config/oauth_token.pickle")
    
    # Verify
    from googleapiclient.discovery import build
    service = build('drive', 'v3', credentials=creds)
    about = service.about().get(fields='user').execute()
    print(f"\nAuthenticated as: {about['user']['emailAddress']}")

if __name__ == "__main__":
    main()
