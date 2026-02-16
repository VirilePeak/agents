import asyncio
from pathlib import Path
from typing import Optional, Dict
from playwright.async_api import async_playwright, Page
import json
import time

class AdScreenshotter:
    """
    Screenshots Facebook Ads from Ad Library.
    
    ToS-Note: This uses browser automation on public pages.
    Facebook may block aggressive scraping.
    Rate limiting and polite delays are implemented.
    """
    
    def __init__(self, output_dir: str = "output/screenshots"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.browser = None
        self.context = None
    
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def screenshot_ad_library(self, brand: str, ad_id: str) -> Optional[Dict]:
        """
        Screenshot a specific ad from Facebook Ad Library.
        
        Args:
            brand: Page/brand name
            ad_id: Facebook ad ID
            
        Returns:
            Dict with paths and metadata, or None if failed
        """
        page = await self.context.new_page()
        
        try:
            # Build Ad Library URL
            url = f"https://www.facebook.com/ads/library/?id={ad_id}"
            
            print(f"Navigating to {url}")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for ad content to load
            await page.wait_for_selector("[data-testid='ad_library_ad']", timeout=10000)
            
            # Take full page screenshot
            timestamp = int(time.time())
            filename = f"{brand}__{ad_id}__{timestamp}.png"
            filepath = self.output_dir / filename
            
            await page.screenshot(path=str(filepath), full_page=False)
            
            # Extract metadata from page
            metadata = await self._extract_metadata(page)
            
            return {
                "screenshot_path": str(filepath),
                "filename": filename,
                "url": url,
                "metadata": metadata
            }
            
        except Exception as e:
            print(f"Error screenshotting ad {ad_id}: {e}")
            return None
        finally:
            await page.close()
    
    async def _extract_metadata(self, page: Page) -> Dict:
        """Extract ad metadata from page"""
        metadata = {
            "headline": "",
            "primary_text": "",
            "cta": "",
            "landing_url": ""
        }
        
        try:
            # Try to extract headline
            headline_elem = await page.query_selector("h2, h3, [role='heading']")
            if headline_elem:
                metadata["headline"] = await headline_elem.inner_text() or ""
            
            # Try to extract CTA button text
            cta_elem = await page.query_selector("button, a[role='button']")
            if cta_elem:
                metadata["cta"] = await cta_elem.inner_text() or ""
            
            # Try to find landing URL
            links = await page.query_selector_all("a[href]")
            for link in links:
                href = await link.get_attribute("href")
                if href and not href.startswith("/") and "facebook.com" not in href:
                    metadata["landing_url"] = href
                    break
                    
        except Exception as e:
            print(f"Error extracting metadata: {e}")
        
        return metadata
    
    async def screenshot_from_csv_row(self, row: Dict) -> Optional[Dict]:
        """
        Screenshot ad from CSV row data.
        
        Expected row fields:
        - brand (Page Name)
        - ad_id or ad_library_id
        - landing_url (optional)
        """
        brand = row.get("brand", row.get("Page Name", "unknown"))
        ad_id = row.get("ad_id", row.get("ad_library_id", ""))
        
        if not ad_id:
            print(f"No ad_id found for {brand}")
            return None
        
        # Rate limiting - be polite
        await asyncio.sleep(2)
        
        result = await self.screenshot_ad_library(brand, ad_id)
        
        if result:
            # Merge with CSV data
            result["csv_data"] = row
            
        return result


async def test_screenshotter():
    """Test the screenshotter"""
    async with AdScreenshotter() as screenshotter:
        # Test with a sample ad ID (replace with real one)
        result = await screenshotter.screenshot_ad_library(
            brand="TestBrand",
            ad_id="123456789"  # Replace with real ad ID
        )
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(test_screenshotter())
