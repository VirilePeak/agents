"""
Google Drive Uploader for Ad-Scout
Uploads screenshots and analysis reports to Google Drive
"""

import os
import json
from pathlib import Path
from typing import Optional, List, Dict
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


class GoogleDriveUploader:
    """
    Uploads files to Google Drive using Service Account.
    
    Requires:
    - Service Account JSON credentials
    - Drive folder shared with service account email
    """
    
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    def __init__(
        self,
        credentials_path: str,
        folder_id: str
    ):
        """
        Initialize uploader
        
        Args:
            credentials_path: Path to service account JSON file
            folder_id: Google Drive folder ID (from URL)
        """
        self.credentials_path = credentials_path
        self.folder_id = folder_id
        self.service = None
        
    def authenticate(self) -> bool:
        """Authenticate with Google Drive API"""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=self.SCOPES
            )
            self.service = build('drive', 'v3', credentials=credentials)
            
            # Test connection
            about = self.service.about().get(fields='user').execute()
            print(f"Authenticated as: {about['user']['emailAddress']}")
            return True
            
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False
    
    def upload_file(
        self,
        file_path: str,
        mime_type: Optional[str] = None,
        custom_name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Upload a file to Google Drive
        
        Args:
            file_path: Local path to file
            mime_type: MIME type (auto-detected if None)
            custom_name: Custom filename in Drive (uses local name if None)
            description: File description
            
        Returns:
            File metadata dict with id, name, webViewLink
        """
        if not self.service:
            print("Not authenticated. Call authenticate() first.")
            return None
        
        path = Path(file_path)
        if not path.exists():
            print(f"File not found: {file_path}")
            return None
        
        try:
            file_metadata = {
                'name': custom_name or path.name,
                'parents': [self.folder_id]
            }
            
            if description:
                file_metadata['description'] = description
            
            # Auto-detect MIME type if not provided
            if not mime_type:
                mime_type = self._get_mime_type(path.suffix)
            
            media = MediaFileUpload(
                str(path),
                mimetype=mime_type,
                resumable=True
            )
            
            print(f"Uploading {path.name}...")
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink, mimeType, size'
            ).execute()
            
            print(f"Uploaded: {file['name']} ({file.get('size', 'unknown')} bytes)")
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
        """
        Upload ad screenshot with structured naming
        
        Args:
            screenshot_path: Path to PNG screenshot
            brand: Brand/page name
            ad_id: Facebook ad ID
            metadata: Additional metadata for description
        """
        # Build descriptive filename
        safe_brand = brand.replace(' ', '_').replace('/', '_')[:30]
        drive_name = f"{safe_brand}__{ad_id}.png"
        
        # Build description from metadata
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
    
    def upload_analysis_report(
        self,
        report_path: str,
        week_name: str
    ) -> Optional[Dict]:
        """
        Upload weekly analysis report
        
        Args:
            report_path: Path to report file (PDF/JSON/CSV)
            week_name: Week identifier (e.g., "2026-W07")
        """
        path = Path(report_path)
        drive_name = f"AdScout_Report_{week_name}{path.suffix}"
        
        mime_type = self._get_mime_type(path.suffix)
        description = f"Weekly Ad Analysis Report - {week_name}"
        
        return self.upload_file(
            file_path=report_path,
            mime_type=mime_type,
            custom_name=drive_name,
            description=description
        )
    
    def list_uploaded_files(self, limit: int = 50) -> List[Dict]:
        """List recently uploaded files in the folder"""
        if not self.service:
            print("Not authenticated.")
            return []
        
        try:
            results = self.service.files().list(
                q=f"'{self.folder_id}' in parents",
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
            '.html': 'text/html'
        }
        return mime_types.get(extension.lower(), 'application/octet-stream')


def create_uploader_from_config(config_path: str = "config/gdrive.json") -> Optional[GoogleDriveUploader]:
    """
    Create uploader from config file
    
    Config format:
    {
        "credentials_path": "/path/to/credentials.json",
        "folder_id": "ABC123"
    }
    """
    try:
        with open(config_path) as f:
            config = json.load(f)
        
        uploader = GoogleDriveUploader(
            credentials_path=config['credentials_path'],
            folder_id=config['folder_id']
        )
        
        if uploader.authenticate():
            return uploader
        return None
        
    except Exception as e:
        print(f"Failed to load config: {e}")
        return None


# Example usage / test
if __name__ == "__main__":
    # For testing - replace with actual paths
    uploader = GoogleDriveUploader(
        credentials_path="config/gdrive_credentials.json",
        folder_id="1ZKo-3BTEmhcbUKLnF0TSSZi56jAhMUU0"
    )
    
    if uploader.authenticate():
        print("Authentication successful!")
        
        # List existing files
        files = uploader.list_uploaded_files(limit=10)
        print(f"\nExisting files in folder: {len(files)}")
        for f in files[:5]:
            print(f"  - {f['name']}")
    else:
        print("Authentication failed!")
