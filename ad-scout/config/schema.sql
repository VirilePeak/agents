-- Ad Scout Database Schema
-- SQLite für einfache Portabilität

-- Ads-Tabelle: Jede einzigartige Ad
CREATE TABLE ads (
    id TEXT PRIMARY KEY,                    -- Ad ID (hash oder FB-ID)
    brand TEXT NOT NULL,                    -- Markenname
    headline TEXT,                          -- Headline der Ad
    primary_text TEXT,                      -- Haupttext
    cta TEXT,                               -- Call-to-Action
    landing_url TEXT,                       -- Ziel-URL
    start_date DATE,                        -- Wann gestartet
    running_since_days INTEGER,             -- Berechnet: Tage seit Start
    format TEXT,                            -- Bild, Video, Carousel
    screenshot_path TEXT,                   -- Lokaler Pfad
    drive_url TEXT,                         -- Google Drive URL
    why_it_works TEXT,                      -- LLM-Analyse
    niche TEXT DEFAULT 'ecommerce_dtc',     -- Nische
    region TEXT DEFAULT 'US_EU',            -- Region
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    week_id TEXT,                           -- z.B. "2026-W07"
    quality_score INTEGER,                  -- 0-100
    UNIQUE(brand, headline, start_date)     -- Dedupe
);

-- Indexe für schnelle Queries
CREATE INDEX idx_ads_week ON ads(week_id);
CREATE INDEX idx_ads_brand ON ads(brand);
CREATE INDEX idx_ads_discovered ON ads(discovered_at);
CREATE INDEX idx_ads_running ON ads(running_since_days);

-- Logs für Monitoring
CREATE TABLE processing_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_id TEXT NOT NULL,
    step TEXT NOT NULL,                     -- 'import', 'screenshot', 'analyze', 'upload'
    status TEXT,                            -- 'success', 'error', 'retry'
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Weekly Summaries
CREATE TABLE weekly_summaries (
    week_id TEXT PRIMARY KEY,
    total_ads INTEGER,
    highlights TEXT,                        -- JSON mit Top 5
    drive_folder_url TEXT,
    sent_at TIMESTAMP
);
