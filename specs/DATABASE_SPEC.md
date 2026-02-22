# Database Specification

## Overview

Introspect uses a normalized relational database to store sales call analysis data. The system supports both **SQLite** (local development) and **PostgreSQL** (production deployment).

---

## Database Schema

### Core Tables

#### `sales_reps`
Sales representatives who conduct calls.

```sql
CREATE TABLE sales_reps (
    email TEXT PRIMARY KEY,
    name TEXT,
    segment TEXT CHECK (segment IN ('enterprise', 'scale', 'velocity', 'unknown')),
    joining_date DATE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

**Fields**:
- `email`: Primary key, unique identifier for rep
- `segment`: Sales segment (enterprise, scale, velocity, unknown)
- `joining_date`: When rep joined the company
- `is_active`: Whether rep is currently active

---

#### `accounts`
Customer accounts identified by email domain.

```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL UNIQUE,
    current_stage TEXT CHECK (current_stage IN ('discovery', 'trial', 'negotiation', 'closed', NULL)),
    deal_status TEXT NOT NULL DEFAULT 'active' CHECK (deal_status IN ('active', 'won', 'lost')),
    primary_sales_rep TEXT,
    primary_segment TEXT,
    first_call_date DATETIME,
    last_call_date DATETIME,
    total_calls INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (primary_sales_rep) REFERENCES sales_reps(email)
);
```

**Fields**:
- `domain`: Unique customer email domain (e.g., "acme.com")
- `current_stage`: Current stage of the deal
- `deal_status`: Overall deal status
- `primary_sales_rep`: Main rep working the account
- `primary_segment`: Segment of primary sales rep
- `first_call_date`/`last_call_date`: Call activity window
- `total_calls`: Total number of calls for this account

**Note**: `current_stage` and `primary_sales_rep` are updated only when processing calls newer than `last_call_date` to handle out-of-order processing.

---

#### `calls`
Individual sales calls.

```sql
CREATE TABLE calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL UNIQUE,
    account_id INTEGER NOT NULL,
    sales_rep_email TEXT NOT NULL,
    call_date DATETIME NOT NULL,
    call_title TEXT,
    primary_stage TEXT CHECK (primary_stage IN ('discovery', 'trial', 'negotiation', 'closed')),
    secondary_stage TEXT CHECK (secondary_stage IN ('discovery', 'trial', 'negotiation', 'closed', NULL)),
    stage_confidence REAL,
    segment_at_call_time TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (sales_rep_email) REFERENCES sales_reps(email)
);
```

**Fields**:
- `call_id`: Gong call ID (unique identifier)
- `primary_stage`: Dominant stage of this call
- `secondary_stage`: Optional secondary theme
- `stage_confidence`: LLM confidence in stage classification (0.0-1.0)
- `segment_at_call_time`: Sales rep's segment at time of call

---

#### `call_participants`
Participants on each call with speaker information.

```sql
CREATE TABLE call_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL,
    speaker_id TEXT NOT NULL,
    party_id TEXT,
    user_id TEXT,
    email_address TEXT,
    name TEXT,
    title TEXT,
    affiliation TEXT CHECK (affiliation IN ('Internal', 'External', 'Unknown', NULL)),
    phone_number TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    UNIQUE(call_id, speaker_id)
);

CREATE INDEX idx_call_participants_call_id ON call_participants(call_id);
CREATE INDEX idx_call_participants_affiliation ON call_participants(affiliation);
```

**Fields**:
- `call_id`: Foreign key to calls
- `speaker_id`: Gong speaker ID (matches transcript speaker IDs)
- `affiliation`: Internal (sales rep), External (customer), or Unknown
- `name`, `title`, `email_address`: Participant details from Gong

**Usage**: Used to enrich transcripts by replacing speaker IDs with meaningful labels like "[Sales - John]" or "[Customer - Sarah]".

---

### Call-Level Score Tables

#### `call_meddpicc_scores`
MEDDPICC evaluation for discovery calls (8 dimensions, 0/2/5 scale).

```sql
CREATE TABLE call_meddpicc_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL UNIQUE,
    metrics INTEGER CHECK (metrics IN (0, 2, 5)),
    economic_buyer INTEGER CHECK (economic_buyer IN (0, 2, 5)),
    decision_criteria INTEGER CHECK (decision_criteria IN (0, 2, 5)),
    decision_process INTEGER CHECK (decision_process IN (0, 2, 5)),
    paper_process INTEGER CHECK (paper_process IN (0, 2, 5)),
    identify_pain INTEGER CHECK (identify_pain IN (0, 2, 5)),
    champion INTEGER CHECK (champion IN (0, 2, 5)),
    competition INTEGER CHECK (competition IN (0, 2, 5)),
    overall_score REAL NOT NULL,
    summary TEXT,
    key_gaps TEXT,
    positive_indicators TEXT,
    coaching_focus TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (call_id) REFERENCES calls(call_id)
);
```

---

#### `call_trial_scores`
Trial health evaluation (5 dimensions, 0/2/5 scale).

```sql
CREATE TABLE call_trial_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL UNIQUE,
    technical_validation INTEGER CHECK (technical_validation IN (0, 2, 5)),
    readiness_progress INTEGER CHECK (readiness_progress IN (0, 2, 5)),
    internal_adoption INTEGER CHECK (internal_adoption IN (0, 2, 5)),
    advocacy_sentiment INTEGER CHECK (advocacy_sentiment IN (0, 2, 5)),
    landscape_competition INTEGER CHECK (landscape_competition IN (0, 2, 5)),
    overall_score REAL NOT NULL,
    health_interpretation TEXT CHECK (health_interpretation IN ('healthy', 'at_risk', 'critical')),
    summary TEXT,
    key_concerns TEXT,
    positive_signals TEXT,
    recommended_actions TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (call_id) REFERENCES calls(call_id)
);
```

---

#### `call_close_scores`
Deal health evaluation for negotiation stage (5 dimensions, 0/2/5 scale).

```sql
CREATE TABLE call_close_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL UNIQUE,
    commercial_alignment INTEGER CHECK (commercial_alignment IN (0, 2, 5)),
    legal_compliance INTEGER CHECK (legal_compliance IN (0, 2, 5)),
    org_consensus INTEGER CHECK (org_consensus IN (0, 2, 5)),
    single_threading_risk INTEGER CHECK (single_threading_risk IN (0, 2, 5)),
    execution_momentum INTEGER CHECK (execution_momentum IN (0, 2, 5)),
    overall_score REAL NOT NULL,
    health_interpretation TEXT CHECK (health_interpretation IN ('healthy', 'at_risk', 'critical')),
    summary TEXT,
    deal_risks TEXT,
    positive_signals TEXT,
    recommended_actions TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (call_id) REFERENCES calls(call_id)
);
```

---

#### `call_win_loss_analysis`
Win/loss analysis for closed deals.

```sql
CREATE TABLE call_win_loss_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL UNIQUE,
    outcome TEXT NOT NULL CHECK (outcome IN ('won', 'lost')),
    primary_reasons TEXT,
    stage_of_decision TEXT,
    critical_dimensions TEXT,
    competitive_factor TEXT,
    key_learnings TEXT,
    verbatim_quotes TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (call_id) REFERENCES calls(call_id)
);
```

---

### Account Aggregation Tables

#### `account_meddpicc_scores`
Aggregated MEDDPICC scores at account level (max per dimension).

```sql
CREATE TABLE account_meddpicc_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL UNIQUE,
    metrics INTEGER CHECK (metrics IN (0, 2, 5)),
    economic_buyer INTEGER CHECK (economic_buyer IN (0, 2, 5)),
    decision_criteria INTEGER CHECK (decision_criteria IN (0, 2, 5)),
    decision_process INTEGER CHECK (decision_process IN (0, 2, 5)),
    paper_process INTEGER CHECK (paper_process IN (0, 2, 5)),
    identify_pain INTEGER CHECK (identify_pain IN (0, 2, 5)),
    champion INTEGER CHECK (champion IN (0, 2, 5)),
    competition INTEGER CHECK (competition IN (0, 2, 5)),
    overall_score REAL NOT NULL,
    based_on_calls INTEGER NOT NULL,
    last_updated DATETIME NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);
```

**Aggregation Logic**: Takes the MAX score for each dimension across all discovery calls.

---

#### `account_trial_health`
Latest trial health for accounts in trial stage.

```sql
CREATE TABLE account_trial_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL UNIQUE,
    technical_validation INTEGER,
    readiness_progress INTEGER,
    internal_adoption INTEGER,
    advocacy_sentiment INTEGER,
    landscape_competition INTEGER,
    overall_score REAL NOT NULL,
    health_interpretation TEXT,
    last_call_id TEXT NOT NULL,
    last_updated DATETIME NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (last_call_id) REFERENCES calls(call_id)
);
```

**Logic**: Takes the most recent trial call scores.

---

#### `account_close_health`
Latest deal health for accounts in negotiation stage.

```sql
CREATE TABLE account_close_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL UNIQUE,
    commercial_alignment INTEGER,
    legal_compliance INTEGER,
    org_consensus INTEGER,
    single_threading_risk INTEGER,
    execution_momentum INTEGER,
    overall_score REAL NOT NULL,
    health_interpretation TEXT,
    last_call_id TEXT NOT NULL,
    last_updated DATETIME NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (last_call_id) REFERENCES calls(call_id)
);
```

**Logic**: Takes the most recent negotiation call scores.

---

### Tracking Tables

#### `stage_transitions`
Tracks when accounts move between stages.

```sql
CREATE TABLE stage_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    from_stage TEXT,
    to_stage TEXT NOT NULL,
    transitioned_at DATETIME NOT NULL,
    duration_in_previous_stage_days INTEGER,
    triggering_call_id TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (triggering_call_id) REFERENCES calls(call_id)
);
```

---

#### `account_rep_history`
Tracks which sales reps have worked on which accounts.

```sql
CREATE TABLE account_rep_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    sales_rep_email TEXT NOT NULL,
    first_call_date DATETIME NOT NULL,
    last_call_date DATETIME NOT NULL,
    total_calls INTEGER NOT NULL DEFAULT 1,
    UNIQUE(account_id, sales_rep_email),
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (sales_rep_email) REFERENCES sales_reps(email)
);
```

---

## Database Support

### SQLite (Local Development)

**File**: `src/data/database.py`

**Usage**:
```python
from src.data import Database, init_database

# Initialize database
db = init_database("introspect.db")

# Get table counts
counts = db.get_table_counts()

# Close
db.close()
```

**Configuration** (`.env`):
```bash
SQLITE_DB_PATH=~/introspect/data/calls.db
```

**Path expansion**:
- `~` → `/Users/username/`
- `$HOME` → `/Users/username/`
- Relative paths: `./data/calls.db`
- Absolute paths: `/Users/username/data/calls.db`

**Priority**: Command line arg > .env > default ("introspect.db")

---

### PostgreSQL (Production)

**File**: `src/data/database_postgres.py`

**Auto-detection**: Detects database type from connection string
- SQLite: file path or `sqlite:///path/to/db`
- PostgreSQL: `postgresql://user:pass@host:port/dbname`

**Usage**:
```python
from src.data.database_postgres import init_database

# SQLite
db = init_database("introspect.db")

# PostgreSQL
db = init_database("postgresql://user:pass@localhost:5432/introspect")

# Cloud SQL
db = init_database("postgresql://user:pass@/introspect?host=/cloudsql/PROJECT:REGION:INSTANCE")
```

**Schema Conversion**: Automatically converts SQLite syntax to PostgreSQL
- `AUTOINCREMENT` → `SERIAL`
- `datetime('now')` → `CURRENT_TIMESTAMP`

---

## Migration

### SQLite to PostgreSQL

**Script**: `migrate_sqlite_to_postgres.py`

**Usage**:
```bash
# Local PostgreSQL
python migrate_sqlite_to_postgres.py \
    --sqlite-path introspect.db \
    --postgres-url "postgresql://user:pass@localhost:5432/introspect"

# Cloud SQL (via cloud-sql-proxy)
python migrate_sqlite_to_postgres.py \
    --sqlite-path introspect.db \
    --postgres-url "postgresql://user:pass@/introspect?host=/cloudsql/PROJECT:REGION:INSTANCE"
```

**Process**:
1. Creates PostgreSQL schema from `schema.sql`
2. Exports all data from SQLite
3. Imports data in batches of 1000 rows
4. Preserves all relationships and constraints

---

## Repository Interface

**File**: `src/data/repository.py`

### Key Methods

**Sales Reps**:
```python
create_sales_rep(rep: SalesRep) -> SalesRep
get_sales_rep(email: str) -> Optional[SalesRep]
list_sales_reps(active_only: bool = False) -> List[SalesRep]
```

**Accounts**:
```python
create_account(account: Account) -> Account
get_account(account_id: int) -> Optional[Account]
get_account_by_domain(domain: str) -> Optional[Account]
update_account(account: Account)
list_accounts() -> List[Account]
```

**Calls**:
```python
create_call(call: Call) -> Call
get_call(call_id: int) -> Optional[Call]
get_call_by_gong_id(gong_call_id: str) -> Optional[Call]
list_calls_by_account(account_id: int) -> List[Call]
```

**Participants**:
```python
store_call_participants(call_id: str, participants: list) -> int
get_call_participants(call_id: str) -> Dict[str, dict]
enrich_transcript_with_participants(call_id: str, transcript: str) -> str
```

**Scores**:
```python
create_call_meddpicc_scores(scores: CallMEDDPICCScores)
get_call_meddpicc_scores(call_id: str) -> Optional[CallMEDDPICCScores]

create_call_trial_scores(scores: CallTrialScores)
get_call_trial_scores(call_id: str) -> Optional[CallTrialScores]

create_call_close_scores(scores: CallCloseScores)
get_call_close_scores(call_id: str) -> Optional[CallCloseScores]

create_call_win_loss_analysis(analysis: CallWinLossAnalysis)
get_call_win_loss_analysis(call_id: str) -> Optional[CallWinLossAnalysis]
```

---

## Transcript Enrichment

### Process

1. **Store Participants**: When processing a call, store participant data from Gong API
   ```python
   repository.store_call_participants(call_id, parties)
   ```

2. **Enrich Transcript**: Replace speaker IDs with meaningful labels
   ```python
   enriched_transcript = repository.enrich_transcript_with_participants(call_id, raw_transcript)
   ```

3. **Pass to Evaluators**: Use enriched transcript for better LLM analysis

### Example

**Raw Transcript**:
```
[2349112610150941359]: Let's discuss your requirements.
[7726781942202217419]: We need to improve our conversion rate.
```

**Enriched Transcript**:
```
[Sales - John]: Let's discuss your requirements.
[Customer - Sarah]: We need to improve our conversion rate.
```

**Benefits**:
- LLM understands who is speaking
- Better context for evaluation
- More accurate scoring

---

## Deployment Options

### Option 1: SQLite + Cloud Storage

**Best for**: < 20 concurrent users, read-heavy workloads

**Setup**:
1. Upload `.db` file to Cloud Storage bucket
2. Download at app startup
3. Read-only in production

**Pros**:
- Zero code changes
- No migration needed
- Low cost (~$1/month)

**Cons**:
- Read-only in production
- Not ideal for concurrent writes

---

### Option 2: Cloud SQL PostgreSQL

**Best for**: Production deployments, concurrent users

**Setup**:
1. Create Cloud SQL instance
2. Run migration script
3. Update connection string in config

**Pros**:
- Handles concurrent users
- Managed backups
- Production-grade

**Cons**:
- Higher cost (~$10-20/month)
- Requires migration

See `DEPLOYMENT_GUIDE.md` for detailed instructions.

---

## Best Practices

### Database Path

**Store data outside repo**:
```bash
# Good
SQLITE_DB_PATH=~/introspect/data/calls.db

# Avoid
SQLITE_DB_PATH=./calls.db  # Inside repo, might commit accidentally
```

### Backups

**Daily backups**:
```bash
cp introspect.db introspect_backup_$(date +%Y%m%d).db
```

### Testing

**Use test database**:
```bash
python process_calls.py --db-path test.db --limit 5
```

### Performance

**Index usage**: Schema includes indexes on:
- `accounts.domain`
- `calls.call_id`
- `calls.account_id`
- `call_participants.call_id`
- `call_participants.affiliation`

---

## Schema Version

**Current Version**: 1.1
- Added `call_participants` table for speaker identification
- Added participant enrichment support

**Previous Version**: 1.0
- Initial schema with 11 tables
- Basic multi-stage evaluation support
