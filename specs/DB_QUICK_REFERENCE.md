# SQLite Database Quick Reference

## Database Location
- **Default**: `./data/calls.db`
- **Configure**: Set `SQLITE_DB_PATH` in `.env`

## Database Statistics (as of 2026-02-12)
- **503 evaluated calls** (discovery + non-discovery)
- **223 accounts** (domains with at least one discovery call)
- **Two tables**: `accounts` (discovery calls with MEDDPICC), `evaluated_calls` (all calls for deduplication)

## View Database Contents

### Option 1: Custom Python Viewers (Easiest)

**View accounts and discovery calls:**
```bash
python view_db.py
```
Shows all accounts with their discovery calls and MEDDPICC scores.

**View all evaluated calls (discovery + rejected):**
```bash
python view_evaluated_calls.py
```
Shows statistics on discovery rate, rejection reasons, and recent calls.

**View MEDDPICC evolution over time:**
```bash
python view_evolution.py
```
Shows how MEDDPICC scores evolved across multiple calls per account.

### Option 2: Command Line (sqlite3)
```bash
# Open database
sqlite3 ./data/calls.db

# Show all tables
.tables

# Show table schema
.schema accounts

# View all accounts
SELECT domain, updated_at FROM accounts;

# View account details (JSON is compact)
SELECT * FROM accounts WHERE domain = 'example.com';

# Count accounts
SELECT COUNT(*) FROM accounts;

# Exit
.quit
```

### Option 3: GUI Tools
1. **DB Browser for SQLite** (Recommended for beginners)
   - Download: https://sqlitebrowser.org/
   - Open `./data/calls.db`
   - Browse Data tab → accounts table

2. **TablePlus** (Modern UI)
   - Download: https://tableplus.com/
   - Create new connection → SQLite
   - Select `./data/calls.db`

## Database Schema

### `accounts` Table (Discovery Calls Only)
Stores all discovery calls grouped by customer domain (external email domain).

| Column | Type | Description |
|--------|------|-------------|
| `domain` | TEXT (PK) | External email domain (e.g., "acme.com") |
| `created_at` | TEXT | ISO 8601 timestamp of first discovery call |
| `updated_at` | TEXT | ISO 8601 timestamp of last/most recent discovery call |
| `calls` | TEXT (JSON) | JSON array of `AccountCall` objects (see structure below) |
| `overall_meddpicc` | TEXT (JSON) | Max MEDDPICC score across all calls for this account |

**Structure of each call in `calls` JSON array:**
```json
{
  "call_id": "string",
  "call_date": "ISO datetime",
  "sales_rep": "email@company.com",
  "external_participants": ["customer@domain.com"],
  "meddpicc_scores": {
    "metrics": 0-5,
    "economic_buyer": 0-5,
    "decision_criteria": 0-5,
    "decision_process": 0-5,
    "paper_process": 0-5,
    "identify_pain": 0-5,
    "champion": 0-5,
    "competition": 0-5,
    "overall_score": 0.0-5.0
  },
  "meddpicc_summary": "Overall summary of MEDDPICC discovery",
  "analysis_notes": {
    "metrics": "Detailed reasoning for metrics score",
    "economic_buyer": "Detailed reasoning for EB score",
    // ... one note per dimension
  }
}
```

### `evaluated_calls` Table (All Calls - Discovery + Non-Discovery)
Tracks all analyzed calls for deduplication. Prevents re-analyzing the same call on subsequent runs.

| Column | Type | Description |
|--------|------|-------------|
| `call_id` | TEXT (PK) | Gong call ID |
| `evaluated_at` | TEXT | ISO 8601 timestamp when call was analyzed |
| `is_discovery` | INTEGER | 1 = discovery call, 0 = not a discovery call |
| `reason` | TEXT (nullable) | Why it's NOT a discovery call (only populated when `is_discovery=0`) |

**Purpose:**
- **Deduplication**: Skip already-analyzed calls (saves LLM costs)
- **Rejection tracking**: Understand why calls aren't discovery calls
- **Analytics**: Track discovery call rate and rejection patterns

## Common Queries

### Accounts Table Queries

#### List all domains with call counts
```sql
SELECT
    domain,
    json_array_length(calls) as call_count,
    json_extract(overall_meddpicc, '$.overall_score') as overall_score,
    updated_at
FROM accounts
ORDER BY updated_at DESC;
```

#### Find accounts with high overall scores (Strong qualification)
```sql
SELECT
    domain,
    json_array_length(calls) as call_count,
    json_extract(overall_meddpicc, '$.overall_score') as score
FROM accounts
WHERE CAST(json_extract(overall_meddpicc, '$.overall_score') AS REAL) >= 4.0
ORDER BY score DESC;
```

#### Find accounts with weak qualification (Red flags)
```sql
SELECT
    domain,
    json_array_length(calls) as call_count,
    json_extract(overall_meddpicc, '$.overall_score') as score
FROM accounts
WHERE json_array_length(calls) >= 3
  AND CAST(json_extract(overall_meddpicc, '$.overall_score') AS REAL) < 3.0
ORDER BY score ASC;
```

#### Find accounts missing economic buyer
```sql
SELECT
    domain,
    json_array_length(calls) as call_count,
    json_extract(overall_meddpicc, '$.economic_buyer') as eb_score,
    json_extract(overall_meddpicc, '$.overall_score') as overall_score
FROM accounts
WHERE CAST(json_extract(overall_meddpicc, '$.economic_buyer') AS INTEGER) <= 2
ORDER BY eb_score ASC;
```

#### Find accounts by MEDDPICC dimension weakness
```sql
-- Weak paper process
SELECT
    domain,
    json_extract(overall_meddpicc, '$.paper_process') as pp_score,
    json_extract(overall_meddpicc, '$.overall_score') as overall_score
FROM accounts
WHERE CAST(json_extract(overall_meddpicc, '$.paper_process') AS INTEGER) <= 2
ORDER BY pp_score ASC;
```

#### Get all MEDDPICC dimensions for an account
```sql
SELECT
    domain,
    json_extract(overall_meddpicc, '$.metrics') as M,
    json_extract(overall_meddpicc, '$.economic_buyer') as E,
    json_extract(overall_meddpicc, '$.decision_criteria') as DC,
    json_extract(overall_meddpicc, '$.decision_process') as DP,
    json_extract(overall_meddpicc, '$.paper_process') as PP,
    json_extract(overall_meddpicc, '$.identify_pain') as IP,
    json_extract(overall_meddpicc, '$.champion') as CH,
    json_extract(overall_meddpicc, '$.competition') as CO,
    json_extract(overall_meddpicc, '$.overall_score') as Overall
FROM accounts
WHERE domain = 'acme.com';
```

### Evaluated Calls Table Queries

#### Get discovery call rate
```sql
SELECT
    SUM(CASE WHEN is_discovery = 1 THEN 1 ELSE 0 END) as discovery_calls,
    SUM(CASE WHEN is_discovery = 0 THEN 1 ELSE 0 END) as non_discovery_calls,
    COUNT(*) as total_calls,
    ROUND(100.0 * SUM(is_discovery) / COUNT(*), 1) as discovery_rate_pct
FROM evaluated_calls;
```

#### View all non-discovery calls with reasons
```sql
SELECT
    call_id,
    evaluated_at,
    reason
FROM evaluated_calls
WHERE is_discovery = 0
ORDER BY evaluated_at DESC
LIMIT 20;
```

#### Count rejection reasons
```sql
SELECT
    reason,
    COUNT(*) as count
FROM evaluated_calls
WHERE is_discovery = 0
  AND reason IS NOT NULL
GROUP BY reason
ORDER BY count DESC;
```

#### Find recently evaluated calls
```sql
SELECT
    call_id,
    evaluated_at,
    CASE WHEN is_discovery = 1 THEN 'Discovery' ELSE 'Not Discovery' END as type,
    reason
FROM evaluated_calls
ORDER BY evaluated_at DESC
LIMIT 20;
```

#### Check if specific call has been evaluated
```sql
SELECT
    call_id,
    is_discovery,
    reason,
    evaluated_at
FROM evaluated_calls
WHERE call_id = 'YOUR_CALL_ID_HERE';
```

## Backup Database
```bash
# Create backup
cp ./data/calls.db ./data/calls_backup_$(date +%Y%m%d).db

# Or use SQLite dump
sqlite3 ./data/calls.db .dump > backup.sql
```

## Reset Database
```bash
# Delete database (will be recreated on next run)
rm ./data/calls.db
```

## Data Flow

1. **Call Fetched from Gong** → LLM classifies as discovery or not
2. **Check `evaluated_calls`** → Skip if already analyzed (deduplication)
3. **If Discovery Call:**
   - Extract domain from first external participant's email
   - Store in `accounts` table:
     - New account created if domain doesn't exist
     - Call added to existing account's calls array
     - `overall_meddpicc` recalculated (max of each dimension)
4. **Store in `evaluated_calls`:**
   - `is_discovery = 1` (no reason)
   - OR `is_discovery = 0` with rejection reason
5. **Real-time Updates** → Both tables updated as each call completes

## Programmatic Access

### Using SQLiteCallRepository (Recommended)

```python
import asyncio
from src.config import load_settings
from src.sqlite_repository import SQLiteCallRepository

async def main():
    settings = load_settings()
    repo = SQLiteCallRepository(settings.sqlite_db_path)

    try:
        # Get all accounts
        accounts = await repo.get_all_accounts()
        print(f"Total accounts: {len(accounts)}")

        # Get specific account
        account = await repo.get_account("acme.com")
        if account:
            print(f"Account: {account.domain}")
            print(f"Discovery calls: {len(account.calls)}")
            print(f"Overall score: {account.overall_meddpicc.overall_score}")

        # Check if call already evaluated
        already_done = await repo.call_exists("call-id-123")
        print(f"Call already evaluated: {already_done}")

        # List all domains
        domains = await repo.list_domains()
        print(f"Domains: {domains}")

    finally:
        await repo.close()

asyncio.run(main())
```

### Direct SQLite Access

```python
import sqlite3
import json

conn = sqlite3.connect('./data/calls.db')
cursor = conn.cursor()

# Get all accounts
cursor.execute("SELECT domain, calls, overall_meddpicc FROM accounts")
for row in cursor.fetchall():
    domain = row[0]
    calls = json.loads(row[1])
    overall = json.loads(row[2])

    print(f"{domain}: {len(calls)} calls, score: {overall['overall_score']}")

conn.close()
```

## Example Account Record

```json
{
  "domain": "acme.com",
  "created_at": "2025-01-15T10:00:00+00:00",
  "updated_at": "2025-01-20T14:30:00+00:00",
  "calls": [
    {
      "call_id": "call-001",
      "call_date": "2025-01-15T10:00:00+00:00",
      "sales_rep": "alice@ourcompany.com",
      "external_participants": ["bob@acme.com", "carol@acme.com"],
      "meddpicc_scores": {
        "metrics": 3,
        "economic_buyer": 2,
        "decision_criteria": 4,
        "decision_process": 3,
        "paper_process": 2,
        "identify_pain": 5,
        "champion": 3,
        "competition": 2,
        "overall_score": 3.0
      },
      "meddpicc_summary": "Strong pain identification but lacks economic buyer access and clear procurement process.",
      "analysis_notes": {
        "metrics": "Mentioned $500K annual cost of downtime but no specific ROI targets discussed.",
        "economic_buyer": "Only spoke with VP Engineering, no CFO or budget holder identified.",
        "decision_criteria": "Clear 8-point evaluation criteria shared by prospect.",
        "decision_process": "3-stage process mentioned but timeline unclear.",
        "paper_process": "No discussion of legal or procurement requirements.",
        "identify_pain": "Exceptional pain discovery: system downtime costing $50K/month, team frustrated.",
        "champion": "VP Engineering supportive but power/influence unclear.",
        "competition": "Competing with status quo, no other vendors mentioned."
      }
    },
    {
      "call_id": "call-002",
      "call_date": "2025-01-20T14:30:00+00:00",
      "sales_rep": "alice@ourcompany.com",
      "external_participants": ["bob@acme.com", "dave@acme.com"],
      "meddpicc_scores": {
        "metrics": 4,
        "economic_buyer": 4,
        "decision_criteria": 4,
        "decision_process": 4,
        "paper_process": 3,
        "identify_pain": 4,
        "champion": 4,
        "competition": 3,
        "overall_score": 3.75
      },
      "meddpicc_summary": "Significant improvement - CFO now engaged with confirmed budget. Still need clarity on paper process timeline.",
      "analysis_notes": {
        "metrics": "$2M annual savings target confirmed by CFO.",
        "economic_buyer": "CFO Dave on call, confirmed $500K budget approved.",
        "decision_criteria": "Reconfirmed 8 criteria, we score highly on 6/8.",
        "decision_process": "Now in stage 2 of 3, expect decision in 4 weeks.",
        "paper_process": "Legal review mentioned as '2 weeks' but details vague.",
        "identify_pain": "Pain reconfirmed, now with executive buy-in.",
        "champion": "VP Bob actively multi-threading us to other stakeholders.",
        "competition": "Also evaluating Competitor X, status quo weakening."
      }
    }
  ],
  "overall_meddpicc": {
    "metrics": 4,           // max(3, 4)
    "economic_buyer": 4,    // max(2, 4) - improved!
    "decision_criteria": 4, // max(4, 4)
    "decision_process": 4,  // max(3, 4) - improved!
    "paper_process": 3,     // max(2, 3) - improved!
    "identify_pain": 5,     // max(5, 4)
    "champion": 4,          // max(3, 4) - improved!
    "competition": 3,       // max(2, 3) - improved!
    "overall_score": 3.75   // max(3.0, 3.75)
  }
}
```

**Note:** The `overall_meddpicc` takes the **maximum** score for each dimension across all calls. This represents the "best understanding achieved" for that account, assuming discovery improves over time.

## Example Evaluated Calls Records

### Discovery Call
```json
{
  "call_id": "1234567890",
  "evaluated_at": "2026-02-12T10:30:00",
  "is_discovery": 1,
  "reason": null
}
```

### Non-Discovery Call (with rejection reason)
```json
{
  "call_id": "9876543210",
  "evaluated_at": "2026-02-12T10:32:00",
  "is_discovery": 0,
  "reason": "This is a post-trial feedback call focused on technical troubleshooting rather than discovery. Customer already trialing product and asking specific feature questions."
}
```

### Common Rejection Reasons
Examples from actual data:
- "Post-trial feedback and technical troubleshooting call"
- "Customer no-show - external participant never joined"
- "Deal navigation and pricing negotiation, not discovery"
- "Existing customer check-in about ongoing usage"
- "Technical demo of specific features, not exploratory"

## Cost Optimization with Deduplication

The `evaluated_calls` table enables **significant cost savings** by preventing re-analysis:

**First run:** 100 calls analyzed → $0.15 cost
**Second run (next day):** 10 new calls, 90 already in `evaluated_calls` → $0.015 cost (90% savings!)

### How Deduplication Works

1. Before analyzing a call, check `evaluated_calls.call_id`
2. If exists: Skip (already analyzed, free!)
3. If not exists: Analyze with LLM (costs ~$0.0015 per call)
4. After analysis: Store result in `evaluated_calls`

### Cost Tracking Query

```sql
SELECT
    COUNT(*) as total_calls,
    SUM(is_discovery) as discovery_calls,
    COUNT(*) - SUM(is_discovery) as rejected_calls,
    ROUND(COUNT(*) * 0.0015, 2) as estimated_cost_usd
FROM evaluated_calls;
```

## Troubleshooting

### Database locked error
- Close any open SQLite connections
- Close DB Browser or other GUI tools
- Check if `view_db.py` or other scripts are still running

### Database not found
- Run the analyzer first: `python main.py --sales-reps your@email.com`
- Check `SQLITE_DB_PATH` in `.env`
- Ensure `./data/` directory exists

### Empty database
- Ensure discovery calls were found during analysis
- Check analyzer output for "Storing to database" messages
- Verify calls have external participants

### JSON parsing errors
- Use `json_extract()` for SQLite queries on JSON columns
- Remember to cast types: `CAST(json_extract(...) AS INTEGER)`
- Use Python's `json.loads()` for programmatic access

### Call not showing up in accounts table
- Check `evaluated_calls` to see if it was classified as non-discovery
- Review rejection reason: `SELECT reason FROM evaluated_calls WHERE call_id = 'xxx'`
- Only discovery calls (is_discovery=1) appear in accounts table

## Performance Tips

### Fast Queries
- ✅ Filter accounts by domain (indexed primary key)
- ✅ Count calls with `json_array_length(calls)`
- ✅ Extract single JSON fields with `json_extract()`

### Slow Queries (use sparingly)
- ⚠️  Iterating through calls JSON arrays in SQL
- ⚠️  Complex JSON operations in WHERE clauses
- ⚠️  Full table scans on evaluated_calls without indexes

**Recommendation:** For complex filtering/aggregation, load data into Python and use the query functions defined in `streamlit_app/utils/db_queries.py`.
