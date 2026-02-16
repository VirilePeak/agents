import csv
from pathlib import Path
from typing import List
from database import Ad, AdDatabase

def parse_facebook_ad_library_csv(csv_path: str) -> List[Ad]:
    """
    Parse Facebook Ad Library CSV export.
    
    Expected CSV columns from Ad Library:
    - Page Name (brand)
    - Ad Creative (headline + text combined)
    - Ad Start Date
    - Ad Status
    - ...
    
    Note: FB CSV format varies. This is a flexible parser.
    """
    ads = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                # Extract brand
                brand = row.get('Page Name', row.get('page_name', 'Unknown'))
                
                # Extract text (FB often combines headline + body)
                full_text = row.get('Ad Creative', row.get('ad_creative', ''))
                
                # Split headline (first line or first 50 chars) and primary text
                lines = full_text.split('\n')
                headline = lines[0][:100] if lines else ""
                primary_text = '\n'.join(lines[1:]) if len(lines) > 1 else full_text[100:500]
                
                # Extract date
                date_str = row.get('Ad Start Date', row.get('ad_start_date', ''))
                # Normalize date format
                start_date = normalize_date(date_str)
                
                # CTA and URL often not in CSV - will be filled by screenshotter
                cta = extract_cta(full_text)
                landing_url = row.get('Landing Page', row.get('landing_page', ''))
                
                ad = Ad(
                    brand=brand.strip(),
                    headline=headline.strip(),
                    primary_text=primary_text.strip(),
                    cta=cta,
                    landing_url=landing_url.strip(),
                    start_date=start_date,
                    format="image"  # Default, screenshotter detects actual format
                )
                
                ads.append(ad)
                
            except Exception as e:
                print(f"Error parsing row: {e}")
                continue
    
    return ads


def normalize_date(date_str: str) -> str:
    """Normalize various date formats to YYYY-MM-DD"""
    from datetime import datetime
    
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y-%m-%d %H:%M:%S",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except:
            continue
    
    # Fallback: today minus 30 days
    from datetime import timedelta
    return (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")


def extract_cta(text: str) -> str:
    """Extract CTA from ad text"""
    ctas = ['shop now', 'learn more', 'sign up', 'get started', 'buy now', 
            'download', 'subscribe', 'join now', 'claim offer', 'order now']
    
    text_lower = text.lower()
    for cta in ctas:
        if cta in text_lower:
            return cta.title()
    
    return "Learn More"  # Default


def import_csv_to_db(csv_path: str, db: AdDatabase, week_id: str) -> dict:
    """Import CSV and return stats"""
    ads = parse_facebook_ad_library_csv(csv_path)
    
    stats = {
        'total_in_csv': len(ads),
        'inserted': 0,
        'duplicates': 0,
        'running_3w_plus': 0
    }
    
    for ad in ads:
        if ad.running_since_days >= 21:
            stats['running_3w_plus'] += 1
        
        inserted = db.insert_ad(ad, week_id)
        if inserted:
            stats['inserted'] += 1
        else:
            stats['duplicates'] += 1
    
    return stats


if __name__ == "__main__":
    # Test with sample CSV
    db = AdDatabase()
    week_id = "2026-W07"
    
    # Create sample CSV for testing
    sample_csv = """Page Name,Ad Creative,Ad Start Date
TestBrand,Get 50% Off Now!\nLimited time offer for our best-selling product. Shop today and save big.,2026-01-15
AnotherCo,New Collection Just Dropped\nCheck out our latest styles. Free shipping on orders over $50.,2026-01-20"""
    
    with open("data/sample_import.csv", "w") as f:
        f.write(sample_csv)
    
    stats = import_csv_to_db("data/sample_import.csv", db, week_id)
    print(f"Import stats: {stats}")
