# Heartbeat Checklist for AlphaClaw

## Daily Checks (rotate through these)

### 1. OpenClaw Version Check
- Run: `openclaw version` or check gateway status
- If version < latest, notify: "New OpenClaw version available. Run 'Update dich' to update."

### 2. Git Status (Ad-Scout Project)
- Check: `cd /root/.openclaw/workspace && git status`
- Notify if uncommitted changes exist > 24h

### 3. Disk Space
- Check: `df -h /root`
- Alert if > 80% full

### 4. Memory Usage
- Check: `free -h`
- Alert if available < 500MB

---

## Weekly Checks

### 1. Dependency Updates
- Check: `pip list --outdated` (in ad-scout)
- Notify if critical packages outdated

### 2. Log Rotation
- Check: `/root/.openclaw/logs/`
- Alert if logs > 100MB

---

## Response Rules

- **Version outdated**: Suggest update, don't auto-update
- **Uncommitted changes**: Remind to commit
- **Resource alerts**: Warn immediately
- **Nothing critical**: HEARTBEAT_OK

## State Tracking

Track last check times in `memory/heartbeat-state.json`:
```json
{
  "lastChecks": {
    "version": 1703275200,
    "git": 1703260800,
    "disk": 1703275200,
    "memory": 1703275200
  }
}
```
