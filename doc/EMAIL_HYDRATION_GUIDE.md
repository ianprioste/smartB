# Customer Email Hydration Strategy

## Overview

The smartBling backend implements a **two-layer email retrieval strategy** to provide customer emails for campaign order exports without overwhelming the Bling API rate limits.

### Problem Statement
- Original implementation: Auto-enriched emails on every page load → excessive API calls → Bling API rate limit (3 req/sec)
- Rate limiting → Cloudflare 429 blocks → Page access blocked
- Need: Supply customer emails without sacrificing system stability

### Solution Architecture

#### Layer 1: Snapshot Persistence (Zero Cost)
- Extract customer email from raw API payloads already stored locally (`raw_order`, `raw_detail`)
- **No extra API calls** during normal UI operation
- Extraction logic safely handles missing/malformed data
- Success rate: ~highest coverage on orders with recent sync

#### Layer 2: Async Hydration (Rate-Limited, Optional)
- Scheduled background task runs periodically outside request path
- Fetches emails for orders with `customer_contact_id` but missing `customer_email`
- **Deduplicates by contact ID**: 18 unique contacts resolve ~33 orders (46% reduction)
- Respects Bling API rate limits (3 req/sec with backoff)
- Gracefully handles 429 rate limits with exponential retry

## Database Schema

```sql
CREATE TABLE bling_order_snapshots (
  -- ... existing columns ...
  customer_email VARCHAR(500),              -- NEW (migration 015)
  customer_contact_id BIGINT,               -- NEW (migration 016)
  -- ... rest of columns ...
);
```

## Configuration

### Environment Variables

| Variable | Default | Purpose | Notes |
|----------|---------|---------|-------|
| `ORDERS_EMAIL_ENRICHMENT_MINUTES` | 0 | Hydration task schedule (minutes) | 0 = disabled; 60 = hourly |
| `ORDERS_EMAIL_ENRICHMENT_BATCH_SIZE` | 20 | Orders per hydration run | Higher = more API calls per cycle |
| `ORDERS_EMAIL_ENRICHMENT_MAX_CONTACTS` | 20 | Max unique contacts per run | Caps API request volume |

### Example Production Setup

```bash
# Enable hydration with conservative defaults (hourly, max 20 contacts)
export ORDERS_EMAIL_ENRICHMENT_MINUTES=60
export ORDERS_EMAIL_ENRICHMENT_BATCH_SIZE=20
export ORDERS_EMAIL_ENRICHMENT_MAX_CONTACTS=20

# Or: hourly with higher volume (max 40 contacts per cycle)
export ORDERS_EMAIL_ENRICHMENT_MINUTES=60
export ORDERS_EMAIL_ENRICHMENT_BATCH_SIZE=50
export ORDERS_EMAIL_ENRICHMENT_MAX_CONTACTS=40
```

## Test Results (2026-04-16)

Manual test with default batch size:

```
Batch: 20 orders (first missing emails)
Unique contacts deduplicated: 18
API calls made: 18 (vs 33 without dedup = 46% savings)
Contacts resolved: 15 (83% success rate)
Rate limit incidents: 1 (gracefully handled with retry)
Runtime: ~110 seconds (including rate limit backoff)
```

### Key Metrics
- **Deduplication effectiveness**: 33 orders → 18 API calls (33% reduction)
- **Contact availability**: 83% of lookups returned email data
- **Rate limit resilience**: Single 429 auto-recovered with backoff
- **Success rate**: 100% of resolved contacts updated to database

## Deployment Guide

### 1. Verify Migrations Applied

```bash
cd backend
python -m alembic current
# Should show: 016_order_snapshot_customer_contact_id

python -m alembic upgrade head
```

### 2. Enable Hydration in Production (Recommended: Start Conservative)

**Phase 1: Hourly hydration with 20 contact max**
```bash
export ORDERS_EMAIL_ENRICHMENT_MINUTES=60
export ORDERS_EMAIL_ENRICHMENT_BATCH_SIZE=20
export ORDERS_EMAIL_ENRICHMENT_MAX_CONTACTS=20
```

**Monitor for 24 hours:**
- Watch logs for `orders_email_hydration_done` messages
- Check Bling API usage: should remain well below rate limit
- Verify email coverage increasing for campaign order exports

**Phase 2: Scale if Stable (After 24h validation)**
```bash
export ORDERS_EMAIL_ENRICHMENT_MINUTES=30       # Every 30 min
export ORDERS_EMAIL_ENRICHMENT_BATCH_SIZE=50    # More orders
export ORDERS_EMAIL_ENRICHMENT_MAX_CONTACTS=40  # More unique contacts
```

### 3. Monitor Task Execution

```bash
# Check recent task logs
docker logs smartbling-backend 2>&1 | grep "orders_email_hydration"

# Or in systemd
journalctl -u smartbling-backend -n 50 | grep "hydration"
```

### Sample Log Output

```
INFO - orders_email_hydration_done contacts_considered=18 contacts_resolved=15 rows_updated=33
```

## API Endpoints

### Get Campaign Orders with Emails

```http
GET /api/events/{campaign_id}/orders?enrich_emails=false
```

Response: Each order includes `customer_email` from:
1. **Snapshot** (highest priority, zero cost)
2. **Raw payload parsing** (fallback if snapshot missing)
3. **Empty** if neither available (hydration will fill later)

## Code References

### Database Model
- [backend/app/models/database.py](../backend/app/models/database.py) - `BlingOrderSnapshotModel` (columns 15-16)

### Data Access Layer
- [backend/app/repositories/order_snapshot_repo.py](../backend/app/repositories/order_snapshot_repo.py)
  - `_extract_customer_email()` - Extracts from raw payloads
  - `_extract_customer_contact_id()` - Extracts contact ID
  - `list_missing_customer_email()` - Queries for hydration target
  - `apply_customer_emails_by_contact_id()` - Bulk update

### Async Tasks
- [backend/app/workers/tasks.py](../backend/app/workers/tasks.py)
  - `hydrate_missing_order_emails_task()` - Main hydration logic

### Scheduler Configuration
- [backend/app/workers/celery_app.py](../backend/app/workers/celery_app.py) - Conditional beat schedule

### API Integration
- [backend/app/api/events.py](../backend/app/api/events.py) - Uses persisted email in response

## Troubleshooting

### Issue: Hydration Task Not Running
**Diagnosis:**
```bash
# Check if Celery beat scheduler is active
ps aux | grep celery
```
**Solution:**
- Verify `ORDERS_EMAIL_ENRICHMENT_MINUTES > 0` is set
- Restart Celery beat: `celery -A app.workers.celery_app beat`

### Issue: Rate Limit Hits (429)
**Expected behavior:** Task auto-retries with exponential backoff
**If persistent:**
- Reduce `ORDERS_EMAIL_ENRICHMENT_MAX_CONTACTS` (fewer parallel calls)
- Increase `ORDERS_EMAIL_ENRICHMENT_MINUTES` (longer between runs)

### Issue: Missing Emails in Campaign Export
**Expected:** Some orders may not have email after hydration (contact deleted, no email on file)
**Workaround:** UI should gracefully handle missing email and show placeholder or "N/A"

## Future Enhancements

1. **Circuit Breaker**: Auto-disable hydration if Bling API unavailable
2. **Metrics Dashboard**: Track hydration success rate, API latency, coverage trends
3. **Selective Backfill**: For orders pre-dating hydration enablement
4. **Contact Cache**: Local cache of recently fetched contacts to reduce API calls
5. **Async UI Trigger**: Allow manual hydration trigger from campaign page

## Related Documentation

- [API.md](./API.md) - Campaign orders endpoint details
- [DEPLOYMENT.md](./DEPLOYMENT.md) - Infrastructure and systemd setup
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System design overview
