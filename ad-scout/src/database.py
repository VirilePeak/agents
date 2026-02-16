import sqlite3
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class Ad:
    brand: str
    headline: str
    primary_text: str
    cta: str
    landing_url: str
    start_date: str
    format: str = "image"
    screenshot_path: Optional[str] = None
    why_it_works: Optional[str] = None
    
    @property
    def id(self) -> str:
        """Generate unique ID from brand + headline + start_date"""
        content = f"{self.brand}|{self.headline}|{self.start_date}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    @property
    def running_since_days(self) -> int:
        """Calculate days since ad started"""
        try:
            start = datetime.strptime(self.start_date, "%Y-%m-%d")
            return (datetime.now() - start).days
        except:
            return 0
    
    @property
    def quality_score(self) -> int:
        """Heuristic quality score 0-100"""
        score = 0
        
        # Running 3+ weeks = +40
        if self.running_since_days >= 21:
            score += 40
        elif self.running_since_days >= 14:
            score += 25
        elif self.running_since_days >= 7:
            score += 10
        
        # Clear CTA = +20
        if self.cta and len(self.cta) > 3:
            score += 20
        
        # Headline with power words = +20
        power_words = ['free', 'now', 'exclusive', 'limited', 'guaranteed', 'proven']
        if any(word in self.headline.lower() for word in power_words):
            score += 20
        
        # Primary text length (not too short, not too long) = +10
        text_len = len(self.primary_text) if self.primary_text else 0
        if 100 <= text_len <= 500:
            score += 10
        
        # Has landing URL = +10
        if self.landing_url and self.landing_url.startswith('http'):
            score += 10
        
        return min(score, 100)


class AdDatabase:
    def __init__(self, db_path: str = "data/adscout.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self.init_db()
    
    def init_db(self):
        """Initialize database with schema"""
        with sqlite3.connect(self.db_path) as conn:
            with open("config/schema.sql") as f:
                conn.executescript(f.read())
    
    def insert_ad(self, ad: Ad, week_id: str) -> bool:
        """Insert ad if not exists. Returns True if inserted, False if duplicate."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO ads (
                        id, brand, headline, primary_text, cta, landing_url,
                        start_date, running_since_days, format, why_it_works,
                        week_id, quality_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ad.id, ad.brand, ad.headline, ad.primary_text, ad.cta,
                    ad.landing_url, ad.start_date, ad.running_since_days,
                    ad.format, ad.why_it_works, week_id, ad.quality_score
                ))
                return True
        except sqlite3.IntegrityError:
            return False  # Duplicate
    
    def get_ads_for_week(self, week_id: str) -> List[Dict]:
        """Get all ads for a specific week"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM ads WHERE week_id = ? ORDER BY quality_score DESC",
                (week_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_top_ads(self, week_id: str, limit: int = 50) -> List[Dict]:
        """Get top N ads by quality score"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM ads 
                WHERE week_id = ? AND running_since_days >= 21
                ORDER BY quality_score DESC 
                LIMIT ?
            """, (week_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def log(self, week_id: str, step: str, status: str, message: str = ""):
        """Log processing step"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO processing_logs (week_id, step, status, message)
                VALUES (?, ?, ?, ?)
            """, (week_id, step, status, message))


if __name__ == "__main__":
    # Test
    db = AdDatabase()
    
    test_ad = Ad(
        brand="TestBrand",
        headline="Get 50% Off Now - Limited Time!",
        primary_text="This is a test ad with some compelling copy that makes you want to click.",
        cta="Shop Now",
        landing_url="https://example.com/offer",
        start_date="2026-01-15",
        format="image"
    )
    
    week_id = datetime.now().strftime("%Y-W%W")
    inserted = db.insert_ad(test_ad, week_id)
    print(f"Inserted: {inserted}, Quality Score: {test_ad.quality_score}")
