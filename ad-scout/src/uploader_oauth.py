"""
Google Drive OAuth Uploader for Ad-Scout - Server Version
Uses OAuth 2.0 with manual code entry (for headless/server environments)
"""

import os
import json
import pickle
from pathlib import Path
from typing import Optional, List, Dict
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


class GoogleDriveOAuthUploader:
    """
    Uploads files to Google Drive using OAuth 2.0
    Works on headless servers with manual code entry
    """
    
    SCOPES = ['https://www.googleapis.com/auth/drive']
    REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'  # Out-of-band for manual entry
    
    def __init__(
        self,
        credentials_path: str = "config/oauth_credentials.json",
        token_path: str = "config/oauth_token.pickle",
        folder_id: str = None
    ):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.folder_id = folder_id
        self.service = None
        self.creds = None
    
    def authenticate(self) -> bool:
        """Authenticate with Google Drive via OAuth (manual flow for servers)"""
        try:
            # Load existing token
            if os.path.exists(self.token_path):
                print("Loading existing token...")
                with open(self.token_path, 'rb') as token:
                    self.creds = pickle.load(token)
            
            # Check if valid
            if self.creds and self.creds.valid:
                print("Token is valid.")
            elif self.creds and self.creds.expired and self.creds.refresh_token:
                print("Refreshing token...")
                self.creds.refresh(Request())
                # Save refreshed token
                with open(self.token_path, 'wb') as token:
                    pickle.dump(self.creds, token)
            else:
                # Need new authentication
                if not os.path.exists(self.credentials_path):
                    print(f"OAuth credentials not found: {self.credentials_path}")
                    return False
                
                print("\n" + "="*60)
                print("GOOGLE DRIVE AUTHENTICATION REQUIRED")
                print("="*60)
                
                # Load client config
                with open(self.credentials_path, 'r') as f:
                    client_config = json.load(f)
                
                # Create flow with out-of-band redirect
                flow = Flow.from_client_config(
                    client_config,
                    scopes=self.SCOPES,
                    redirect_uri=self.REDIRECT_URI
                )
                
                # Generate auth URL
                auth_url, _ = flow.authorization_url(prompt='consent')
                
                print("\n1. Open this URL in your browser:")
                print("-" * 60)
                print(auth_url)
                print("-" * 60)
                
                print("\n2. Sign in with your Google account")
                print("3. Grant permission for Drive access")
                print("4. Copy the authorization code")
                print("\nEnter the authorization code here:")
                
                # In headless environment, we can't use input()
                # So we save the URL to a file and wait
                with open('config/auth_url.txt', 'w') as f:
                    f.write(auth_url)
                
                print("\n⚠️  Auth URL saved to: config/auth_url.txt")
                print("   Open this URL in your browser, then create:")
                print("   config/auth_code.txt")
                print("   ...with the authorization code.")
                
                # Check for auth code file
                code_file = 'config/auth_code.txt'
                if os.path.exists(code_file):
                    with open(code_file, 'r') as f:
                        code = f.read().strip()
                    
                    print(f"\nFound auth code, completing flow...")
                    flow.fetch_token(code=code)
                    self.creds = flow.credentials
                    
                    # Save token
                    os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
                    with open(self.token_path, 'wb') as token:
                        pickle.dump(self.creds, token)
                    
                    # Clean up
                    os.remove(code_file)
                    print("✅ Token saved!")
                else:
                    print("\n⏳ Waiting for auth code...")
                    print(f"   Please create {code_file} with the code from Google.")
                    return False
            
            # Build service
            self.service = build('drive', 'v3', credentials=self.creds)
            
            # Test connection
            about = self.service.about().get(fields='user').execute()
            print(f"\n✅ Authenticated as: {about['user']['emailAddress']}")
            return True
            
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False
    
    def complete_auth_with_code(self, code: str) -> bool:
        """
        Complete authentication with manually provided code
        
        Args:
            code: The authorization code from Google
        """
        try:
            with open(self.credentials_path, 'r') as f:
                client_config = json.load(f)
            
            flow = Flow.from_client_config(
                client_config,
                scopes=self.SCOPES,
                redirect_uri=self.REDIRECT_URI
            )
            
            flow.fetch_token(code=code)
            self.creds = flow.credentials
            
            # Save token
            os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
            with open(self.token_path, 'wb') as token:
                pickle.dump(self.creds, token)
            
            # Build service
            self.service = build('drive', 'v3', credentials=self.creds)
            
            about = self.service.about().get(fields='user').execute()
            print(f"✅ Authenticated as: {about['user']['emailAddress']}")
            return True
            
        except Exception as e:
            print(f"Failed to complete auth: {e}")
            return False
    
    def upload_file(
        self,
        file_path: str,
        mime_type: Optional[str] = None,
        custom_name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[Dict]:
        """Upload a file to Google Drive"""
        if not self.service:
            print("Not authenticated. Call authenticate() first.")
            return None
        
        path = Path(file_path)
        if not path.exists():
            print(f"File not found: {file_path}")
            return None
        
        try:
            file_metadata = {'name': custom_name or path.name}
            
            if self.folder_id:
                file_metadata['parents'] = [self.folder_id]
            
            if description:
                file_metadata['description'] = description
            
            if not mime_type:
                mime_type = self._get_mime_type(path.suffix)
            
            media = MediaFileUpload(str(path), mimetype=mime_type, resumable=True)
            
            print(f"Uploading {path.name}...")
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink, mimeType, size'
            ).execute()
            
            print(f"✅ Uploaded: {file['name']}")
            print(f"Link: {file['webViewLink']}")
            
            return file
            
        except HttpError as e:
            print(f"Upload failed: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None
    
    def upload_screenshot(
        self,
        screenshot_path: str,
        brand: str,
        ad_id: str,
        metadata: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Upload ad screenshot with structured naming"""
        safe_brand = brand.replace(' ', '_').replace('/', '_')[:30]
        drive_name = f"{safe_brand}__{ad_id}.png"
        
        description = f"Ad screenshot for {brand}\nAd ID: {ad_id}"
        if metadata:
            if metadata.get('headline'):
                description += f"\nHeadline: {metadata['headline'][:100]}"
            if metadata.get('landing_url'):
                description += f"\nLanding: {metadata['landing_url'][:100]}"
        
        return self.upload_file(
            file_path=screenshot_path,
            mime_type='image/png',
            custom_name=drive_name,
            description=description
        )
    
    def list_files(self, limit: int = 50) -> List[Dict]:
        """List files in Drive"""
        if not self.service:
            print("Not authenticated.")
            return []
        
        try:
            query = f"'{self.folder_id}' in parents" if self.folder_id else None
            
            results = self.service.files().list(
                q=query,
                pageSize=limit,
                fields="files(id, name, createdTime, webViewLink, size)"
            ).execute()
            
            return results.get('files', [])
            
        except Exception as e:
            print(f"Failed to list files: {e}")
            return []
    
    def _get_mime_type(self, extension: str) -> str:
        """Get MIME type from file extension"""
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf',
            '.json': 'application/json',
            '.csv': 'text/csv',
            '.txt': 'text/plain',
            '.md': 'text/markdown',
        }
        return mime_types.get(extension.lower(), 'application/octet-stream')


def main():
    """Test OAuth uploader"""
    uploader = GoogleDriveOAuthUploader(
        credentials_path="config/oauth_credentials.json",
        token_path="config/oauth_token.pickle",
        folder_id="1ZKo-3BTEmhcbUKLnF0TSSZi56jAhMUU0"
    )
    
    # Try to authenticate
    if uploader.authenticate():
        print("\n✅ Ready to upload!")
        
        # Test upload
        test_content = "Ad-Scout OAuth Test\nTimestamp: 2026-02-17"
        with open('output/test_oauth.txt', 'w') as f:
            f.write(test_content)
        
        result = uploader.upload_file(
            file_path='output/test_oauth.txt',
            custom_name='Test_OAuth_Upload.txt',
            description='Test file via OAuth authentication'
        )
        
        if result:
            print(f"\n✅ Test upload successful!")
            print(f"File: {result['webViewLink']}")
    else:
        print("\n⏳ Authentication pending...")
        print("Check config/auth_url.txt and follow the instructions.")


if __name__ == "__main__":
    main()
