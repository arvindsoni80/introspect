# SQLite Database Quick Reference

## Database Location
- **Default**: `./data/calls.db`
- **Configure**: Set `SQLITE_DB_PATH` in `.env`

## View Database Contents

### Option 1: Custom Python Viewer (Easiest)
```bash
python view_db.py
```
Shows all accounts with their discovery calls and MEDDPICC scores.

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

### `accounts` Table
| Column | Type | Description |
|--------|------|-------------|
| `domain` | TEXT (PK) | External email domain (e.g., "example.com") |
| `created_at` | TEXT | ISO 8601 timestamp of first discovery call |
| `updated_at` | TEXT | ISO 8601 timestamp of last discovery call |
| `calls` | TEXT (JSON) | Array of discovery calls with MEDDPICC scores |
| `overall_meddpicc` | TEXT (JSON) | Max MEDDPICC score across all calls |

## Common Queries

### List all domains with call counts
```sql
SELECT
    domain,
    json_array_length(calls) as call_count,
    updated_at
FROM accounts
ORDER BY updated_at DESC;
```

### Find accounts with high overall scores
```sql
SELECT
    domain,
    json_extract(overall_meddpicc, '$.overall_score') as score
FROM accounts
WHERE CAST(json_extract(overall_meddpicc, '$.overall_score') AS REAL) >= 4.0
ORDER BY score DESC;
```

### Find accounts missing economic buyer
```sql
SELECT
    domain,
    json_extract(overall_meddpicc, '$.economic_buyer') as eb_score
FROM accounts
WHERE CAST(json_extract(overall_meddpicc, '$.economic_buyer') AS INTEGER) <= 2
ORDER BY eb_score;
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

1. **Discovery Call Analyzed** → Stored in database
2. **Domain Extraction** → First external participant's email domain
3. **Account Update** →
   - New account created if domain doesn't exist
   - Call added to existing account
   - `overall_meddpicc` recalculated (max of each dimension)
4. **Real-time Updates** → Database updated as each call completes

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
      }
    }
  ],
  "overall_meddpicc": {
    "metrics": 4,           // max(3, 4)
    "economic_buyer": 4,    // max(2, 4)
    "decision_criteria": 4, // max(4, 4)
    "decision_process": 4,  // max(3, 4)
    "paper_process": 3,     // max(2, 3)
    "identify_pain": 5,     // max(5, 4)
    "champion": 4,          // max(3, 4)
    "competition": 3,       // max(2, 3)
    "overall_score": 3.75   // max(3.0, 3.75)
  }
}
```

## Troubleshooting

### Database locked error
- Close any open SQLite connections
- Close DB Browser or other GUI tools

### Database not found
- Run the analyzer first: `python main.py --sales-reps your@email.com --post-slack`
- Check `SQLITE_DB_PATH` in `.env`

### Empty database
- Ensure discovery calls were found during analysis
- Check analyzer output for "Storing to database" messages
