"""
Upload workflow for Ad-Scout
Uploads screenshots and reports to Google Drive
"""

import asyncio
import json
from pathlib import Path
from typing import List, Dict, Optional
from uploader import GoogleDriveUploader, create_uploader_from_config
from database import Database


class UploadWorkflow:
    """
    Manages upload workflow for ad screenshots and analysis
    """
    
    def __init__(
        self,
        uploader: GoogleDriveUploader,
        db: Database
    ):
        self.uploader = uploader
        self.db = db
    
    async def upload_pending_screenshots(self) -> List[Dict]:
        """
        Upload all pending screenshots from database
        
        Returns:
            List of upload results
        """
        # Get ads without drive_url
        pending = self.db.get_ads_without_drive_url()
        
        results = []
        for ad in pending:
            screenshot_path = ad.get('screenshot_path')
            
            if not screenshot_path or not Path(screenshot_path).exists():
                print(f"Screenshot not found for ad {ad['ad_id']}")
                continue
            
            # Upload to Drive
            result = self.uploader.upload_screenshot(
                screenshot_path=screenshot_path,
                brand=ad.get('brand', 'Unknown'),
                ad_id=ad['ad_id'],
                metadata={
                    'headline': ad.get('headline', ''),
                    'landing_url': ad.get('landing_url', '')
                }
            )
            
            if result:
                # Update database with Drive URL
                self.db.update_ad_drive_url(
                    ad_id=ad['ad_id'],
                    drive_url=result['webViewLink'],
                    drive_file_id=result['id']
                )
                
                results.append({
                    'ad_id': ad['ad_id'],
                    'drive_url': result['webViewLink'],
                    'status': 'success'
                })
            else:
                results.append({
                    'ad_id': ad['ad_id'],
                    'status': 'failed'
                })
            
            # Rate limiting
            await asyncio.sleep(0.5)
        
        return results
    
    async def upload_weekly_bundle(
        self,
        week_folder: str,
        report_path: Optional[str] = None
    ) -> Dict:
        """
        Upload all files for a week as a bundle
        
        Args:
            week_folder: Path to week's screenshot folder
            report_path: Optional path to analysis report
        """
        results = {
            'screenshots': [],
            'report': None,
            'errors': []
        }
        
        # Upload screenshots
        screenshot_dir = Path(week_folder)
        if screenshot_dir.exists():
            for screenshot in screenshot_dir.glob("*.png"):
                try:
                    # Parse filename: Brand__ad_id__timestamp.png
                    parts = screenshot.stem.split('__')
                    brand = parts[0] if len(parts) > 0 else 'Unknown'
                    ad_id = parts[1] if len(parts) > 1 else 'unknown'
                    
                    result = self.uploader.upload_screenshot(
                        screenshot_path=str(screenshot),
                        brand=brand,
                        ad_id=ad_id
                    )
                    
                    if result:
                        results['screenshots'].append({
                            'name': screenshot.name,
                            'drive_url': result['webViewLink']
                        })
                    
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    results['errors'].append(f"{screenshot.name}: {e}")
        
        # Upload report if provided
        if report_path and Path(report_path).exists():
            week_name = Path(week_folder).name
            result = self.uploader.upload_analysis_report(
                report_path=report_path,
                week_name=week_name
            )
            
            if result:
                results['report'] = {
                    'name': Path(report_path).name,
                    'drive_url': result['webViewLink']
                }
        
        return results


async def main():
    """Test upload workflow"""
    
    # Initialize uploader
    uploader = create_uploader_from_config("config/gdrive.json")
    
    if not uploader:
        print("Failed to initialize uploader")
        return
    
    print("Upload workflow ready!")
    print(f"Target folder: {uploader.folder_id}")
    
    # List existing files
    files = uploader.list_uploaded_files(limit=10)
    print(f"\n{len(files)} files already in Drive folder")


if __name__ == "__main__":
    asyncio.run(main())
