# Content Automation (n8n + Postgres)

This project runs an 8-workflow content automation system for YouTube Shorts, TikTok, and Instagram Reels.
Single source of truth is Postgres (`content_automation`).

## Requirements
- Docker + Docker Compose
- n8n instance running in the same Docker network as Postgres

## Services / Network
- Postgres container name: `postgres`
- n8n container name: `n8n` (example)
- Same Docker network required.

## URLs & Ports
| Service | URL | Port | Notes |
|---------|-----|------|-------|
| n8n UI | http://localhost:5678 | 5678 | Web interface |
| Postgres | localhost:5432 | 5432 | Local debugging only |

## PostgreSQL Credentials (n8n)
| Setting | Value |
|---------|-------|
| Host | `postgres` |
| Port | `5432` |
| Database | `content_automation` |
| User | `content` |
| Password | `content_pass` |
| SSL | disabled |

## Database Initialization
Schema is created from `init.sql` on first start via:
```
/docker-entrypoint-initdb.d/init.sql
```

## Verify Installation (2 minutes)
```bash
# Check containers are running
docker compose ps

# Verify database schema exists
docker exec -it postgres psql -U content -d content_automation -c "\dt"
```

Expected output: 10 tables (runs, content_ideas, scripts, assets, qa_results, approvals, publish_queue, analytics_daily, hooks_library, patterns_library)

## Workflows (n8n)

| # | Workflow | Trigger | Time |
|---|----------|---------|------|
| 1 | Trend Discovery | Cron | Daily 06:00 |
| 2 | Script Generation | Cron | Daily 07:00 |
| 3 | Production Assets | Cron | Daily 08:00 |
| 4 | QA & Compliance | Postgres trigger | on insert |
| 5 | Human Approval Gate | Postgres + Webhook | on qa_passed |
| 6 | Scheduling & Publishing | Postgres trigger | on approved |
| 7 | Analytics Loop | Cron | Daily 18:00 + Sun 09:00 |
| 8 | Content Library Maintenance | Cron | Sun 10:00 |

## Feature/Behavior Rules
- ✅ Captions are **English only**
- ✅ **No hashtags** in output
- ✅ Publishing includes a **human approval gate**
- ✅ If a platform API is missing, the workflow outputs **Publish Pending / Manual Required** (never claim posted)

## Quick Start

### 1. Create .env file
```bash
cp .env.example .env
# Edit .env and set your credentials
```

### 2. Start containers
```bash
docker compose up -d
```

### 3. Verify installation
```bash
docker compose ps
docker exec -it postgres psql -U content -d content_automation -c "\dt"
```

### 4. Access n8n
Open http://localhost:5678

Login credentials are set via `.env`:
- `N8N_BASIC_AUTH_USER` (default: admin)
- `N8N_BASIC_AUTH_PASSWORD` (default: changeme)

⚠️ **Change the default password in production!**

### 5. Set n8n credentials
- Add **Postgres** credential using the values above
- Add **OpenAI** credential
- Optional: Telegram/Email/Slack for approvals

### 6. Activate workflows in order:
```
1 → 2 → 3 → 4 → 5 → 6 → 7 → 8
```

## First Run Test (End-to-End)

### Step 1: Run Workflow 1 (Trend Discovery)
Execute manually in n8n → Check: `SELECT * FROM content_ideas;`

### Step 2: Run Workflow 2 (Script Generation)
Execute manually → Check: `SELECT * FROM scripts;`

### Step 3: Run Workflow 3 (Production Assets)
Execute manually → Check: `SELECT * FROM assets;`

### Step 4: QA Check
Insert QA result: `INSERT INTO qa_results (idea_id, passed, issues, notes) SELECT id, true, '[]', 'test' FROM content_ideas LIMIT 1;`
Update script: `UPDATE scripts SET status='qa_passed' WHERE id IN (SELECT id FROM scripts LIMIT 1);`
→ Workflow 4 & 5 should trigger

### Step 5: Approval
Check Telegram/Email for approval request, or insert directly:
```sql
INSERT INTO approvals (idea_id, decision, notes, decided_by) 
SELECT id, 'approve', 'test', 'admin' FROM content_ideas WHERE status='qa' LIMIT 1;
UPDATE scripts SET status='approved' WHERE idea_id IN (SELECT idea_id FROM approvals WHERE decision='approve');
```
→ Workflow 6 should trigger, creating entries in `publish_queue`

## Smoke Test (Quick)

Insert a demo idea:
```bash
docker exec -it postgres psql -U content -d content_automation -c \
"INSERT INTO content_ideas (idea_hash, niche, title, premise, sources, freshness_score, potential_score, status)
 VALUES ('hash_demo_001','dtc','Demo idea','Demo premise','[\"demo\"]',0.9,0.9,'new')
 ON CONFLICT (idea_hash) DO NOTHING;"
```

Then run:
- **Workflow 2** (Script Generation) manually in n8n

Verify scripts table:
```bash
docker exec -it postgres psql -U content -d content_automation -c "SELECT variant, left(script_text,80) FROM scripts LIMIT 10;"
```

## Data Persistence

Data is stored in Docker volumes:
- `postgres_data` - Database files
- `n8n_data` - n8n workflows and credentials

⚠️ **WARNING:** `docker compose down -v` deletes ALL data permanently!

Backup before destructive operations:
```bash
docker exec postgres pg_dump -U content content_automation > backup.sql
```

## Security Notes

- ✅ Set n8n auth via `.env` (`N8N_BASIC_AUTH_USER` / `N8N_BASIC_AUTH_PASSWORD`). Do not hardcode credentials in docs.
- ✅ Never commit `.env` or credential JSON files (Google OAuth/Drive).
- ✅ Add to `.gitignore`:
  ```
  .env
  *.json
  credentials/
  backup.sql
  ```

## Common Issues

### n8n cannot reach Postgres:
- Ensure both containers are in the **same network**
- Host must be `postgres` (container name), **not localhost**

### Schema not created:
- Ensure `init.sql` is mounted into `/docker-entrypoint-initdb.d/`
- Check: `docker exec postgres ls /docker-entrypoint-initdb.d/`

### Workflow triggers not firing:
- Postgres trigger workflows need the **Postgres Trigger node** (not just query)
- Ensure the trigger is connected to the correct table/column

## Dashboard Queries

Daily throughput:
```sql
SELECT date_trunc('day', created_at)::date AS day,
       count(*) FILTER (WHERE status='new') AS new_ideas,
       count(*) FILTER (WHERE status='published') AS published
FROM content_ideas
WHERE created_at >= now() - interval '14 days'
GROUP BY 1 ORDER BY 1 DESC;
```

Queue health:
```sql
SELECT platform, status, count(*) FROM publish_queue GROUP BY platform, status;
```

Stuck items:
```sql
SELECT id, title, status, updated_at,
       extract(epoch from (now() - updated_at))/3600 as hours_stuck
FROM content_ideas
WHERE updated_at < now() - interval '24 hours'
  AND status IN ('new','scripted','assets_ready','qa','approved','scheduled')
ORDER BY updated_at ASC;
```

## Environment Variables (n8n)

Set in n8n: **Settings → Variables**

```bash
# Required
OPENAI_API_KEY=sk-xxxxxxxxxxxx
DB_HOST=postgres
DB_PORT=5432
DB_NAME=content_automation
DB_USER=content
DB_PASSWORD=content_pass

# Optional
TELEGRAM_BOT_TOKEN=xxxxxx:xxxxxxxxxxxx
TELEGRAM_CHAT_ID=123456789
YOUTUBE_API_KEY=AIzaxxxxxxxxxxxx
NICHE=entrepreneurship
TARGET_AUDIENCE="aspiring entrepreneurs aged 25-35"
```

## File Structure
```
.
├── docker-compose.yml    # Service definitions
├── init.sql              # Database schema (auto-executed)
├── .env                  # Credentials (NEVER COMMIT)
└── README.md             # This file
```

## Support
- n8n docs: https://docs.n8n.io
- Postgres docs: https://www.postgresql.org/docs/
