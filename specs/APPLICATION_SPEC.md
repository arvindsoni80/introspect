# Application Specification

## Overview

Introspect is a multi-stage sales call analysis system that automatically evaluates Gong call transcripts using stage-appropriate frameworks and provides actionable insights through Streamlit dashboards.

### System Goals

1. **Automatic Stage Classification**: Classify calls into discovery, trial, negotiation, or closed
2. **Stage-Appropriate Evaluation**: Apply the right framework (MEDDPICC, TRIAL, CLOSE, Win/Loss)
3. **Quantitative Scoring**: Consistent 0/2/5 scoring for objective measurement
4. **Account Tracking**: Track accounts across stages with full history
5. **Coaching Insights**: Identify weaknesses and provide actionable recommendations

---

## Architecture

### System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                          GONG API                                │
│                    (Source of Truth)                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ Fetch Calls + Participants
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     CALL PROCESSOR                               │
│                  (Orchestrates Flow)                             │
│                                                                  │
│  1. Extract metadata (rep, account, date)                       │
│  2. Store participants (for speaker identification)             │
│  3. Enrich transcript with participant names/roles              │
│  4. Classify stage                                               │
│  5. Route to evaluator                                           │
│  6. Save results                                                 │
│  7. Update account state                                         │
└──────────────┬──────────────┬──────────────┬────────────────────┘
               │              │              │
     ┌─────────▼─────┐  ┌────▼─────┐  ┌────▼─────┐
     │ Discovery     │  │  Trial   │  │Negotiation│
     │  (MEDDPICC)   │  │ (TRIAL)  │  │ (CLOSE)   │
     │               │  │          │  │           │
     │ 8 dimensions  │  │5 dims    │  │5 dims     │
     │ 0/2/5 scale   │  │0/2/5     │  │0/2/5      │
     └───────────────┘  └──────────┘  └───────────┘
               │              │              │
               └──────────────┴──────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SQLite DATABASE                             │
│                    (12 Normalized Tables)                        │
│                                                                  │
│  Core:         accounts, calls, sales_reps                      │
│  Participants: call_participants                                 │
│  Call Scores:  call_meddpicc_scores, call_trial_scores, ...    │
│  Aggregates:   account_meddpicc_scores, account_trial_health   │
│  Tracking:     stage_transitions, account_rep_history          │
└─────────────────────────────────────────────────────────────────┘
               │              │              │
               └──────────────┴──────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   STREAMLIT DASHBOARDS                           │
│                                                                  │
│  • Home: Overview and navigation                                 │
│  • Accounts: Account details, contacts, call history            │
│  • Calls: Call analysis, transcripts, scores                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Code Organization

```
src/
├── core/                    🔧 Infrastructure Layer
│   ├── config.py           → Environment config (.env loading)
│   ├── gong_client.py      → Gong API client (calls, transcripts)
│   └── llm_client.py       → LLM client (Anthropic Claude)
│
├── domain/                  🎯 Business Entities
│   ├── sales_rep.py        → SalesRep model
│   ├── account.py          → Account, StageTransition, AccountRepHistory
│   ├── call.py             → Call, StageClassificationResult
│   └── scores.py           → All score types (16 dataclasses)
│       ├── MEDDPICCScores       (discovery)
│       ├── TrialScores          (trial)
│       ├── CloseScores          (negotiation)
│       └── WinLossAnalysis      (closed)
│
├── data/                    💾 Persistence Layer
│   ├── schema.sql          → Database schema (12 tables)
│   ├── database.py         → SQLite connection management
│   ├── database_postgres.py → PostgreSQL support
│   └── repository.py       → CRUD operations (~1200 lines)
│       ├── Sales Rep operations
│       ├── Account operations
│       ├── Call operations
│       ├── Participant operations
│       └── Score operations
│
└── services/                ⚙️ Business Logic Layer
    ├── stage_classifier.py      → Classify call stage
    ├── call_processor.py        → Orchestrate flow
    └── evaluators/
        ├── meddpicc_evaluator.py    → Discovery
        ├── trial_evaluator.py       → Trial
        ├── close_evaluator.py       → Negotiation
        └── winloss_analyzer.py      → Closed

streamlit_app/
├── Home.py                  → Landing page
└── pages/
    ├── 2_accounts.py        → Account dashboard
    └── 3_calls.py           → Call analysis dashboard
```

---

## Processing Pipeline

### Call Processing Flow

```
┌──────────────────────────────────────────────────────────────────┐
│ Step 1: FETCH CALL                                               │
├──────────────────────────────────────────────────────────────────┤
│ Input:  Gong call ID                                             │
│ Action: GongClient.get_calls_for_sales_reps()                    │
│ Output: {metaData, parties, ...} + transcript                    │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 2: EXTRACT METADATA                                         │
├──────────────────────────────────────────────────────────────────┤
│ • Sales rep email (internal participant)                         │
│ • Customer domain (external participant)                         │
│ • Call date and title                                            │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 3: ENSURE ENTITIES EXIST                                    │
├──────────────────────────────────────────────────────────────────┤
│ • Get/Create SalesRep                                            │
│ • Get/Create Account (by domain)                                 │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 4: CLASSIFY STAGE                                           │
├──────────────────────────────────────────────────────────────────┤
│ Input:  Transcript + Title                                       │
│ LLM:    Claude analyzes content                                  │
│ Output: {primary_stage, confidence, secondary_stage, reasoning}  │
│                                                                  │
│ Possible stages:                                                 │
│   • discovery    → First meetings, qualification                │
│   • trial        → POC, product testing                         │
│   • negotiation  → Pricing, contracts, closing                  │
│   • closed       → Won/lost discussions                         │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 5: CREATE CALL RECORD                                       │
├──────────────────────────────────────────────────────────────────┤
│ Repository.create_call()                                         │
│ → Saves to `calls` table with stage classification              │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 6: STORE PARTICIPANTS                                       │
├──────────────────────────────────────────────────────────────────┤
│ Repository.store_call_participants(call_id, parties)             │
│ → Stores speaker_id, name, title, email, affiliation            │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 7: ENRICH TRANSCRIPT                                        │
├──────────────────────────────────────────────────────────────────┤
│ Repository.enrich_transcript_with_participants()                 │
│ → Replaces speaker IDs with "[Role - Name]" labels              │
│ → Example: [2349...] → [Sales - John]                          │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 8: EVALUATE (Stage-Specific)                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│ IF discovery:                                                     │
│   ├─→ MEDDPICCEvaluator.evaluate(enriched_transcript)           │
│   ├─→ Scores: M, E, D, D, P, I, C, C (0/2/5 each)              │
│   └─→ Save to call_meddpicc_scores                              │
│                                                                  │
│ IF trial:                                                         │
│   ├─→ TrialEvaluator.evaluate(enriched_transcript)              │
│   ├─→ Scores: T, R, I, A, L (0/2/5 each)                       │
│   └─→ Save to call_trial_scores                                 │
│                                                                  │
│ IF negotiation:                                                   │
│   ├─→ CloseEvaluator.evaluate(enriched_transcript)              │
│   ├─→ Scores: C, L, O, S, E (0/2/5 each)                       │
│   └─→ Save to call_close_scores                                 │
│                                                                  │
│ IF closed:                                                        │
│   ├─→ WinLossAnalyzer.evaluate(enriched_transcript)             │
│   ├─→ Analysis: outcome, reasons, learnings                     │
│   └─→ Save to call_win_loss_analysis                            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 9: UPDATE ACCOUNT STATE                                     │
├──────────────────────────────────────────────────────────────────┤
│ • Set current_stage (only if call is newer than last_call_date) │
│ • Update first_call_date / last_call_date                       │
│ • Increment total_calls                                          │
│ • Repository.update_account()                                    │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 10: UPDATE ACCOUNT-REP HISTORY                              │
├──────────────────────────────────────────────────────────────────┤
│ • Track which reps worked on this account                       │
│ • Update call counts per rep                                     │
│ • Repository.upsert_account_rep_history()                        │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ ✅ COMPLETE                                                       │
├──────────────────────────────────────────────────────────────────┤
│ • Call classified and evaluated                                 │
│ • Participants stored and transcript enriched                   │
│ • Scores stored in database                                      │
│ • Account state updated                                          │
│ • Ready for dashboard visualization                             │
└──────────────────────────────────────────────────────────────────┘
```

---

## Evaluation Frameworks

### MEDDPICC (Discovery) - 8 Dimensions

**Goal**: Qualify the opportunity

```
┌──────────────────────────────────────────────────────────────┐
│ M  Metrics              │ 0: None  │ 2: Generic │ 5: Specific │
│ E  Economic Buyer       │ 0: None  │ 2: Unclear │ 5: Confirmed│
│ D  Decision Criteria    │ 0: None  │ 2: Informal│ 5: Documented│
│ D  Decision Process     │ 0: None  │ 2: Partial │ 5: Mapped    │
│ P  Paper Process        │ 0: None  │ 2: Some    │ 5: Detailed  │
│ I  Identify Pain        │ 0: Vague │ 2: Clear   │ 5: Urgent    │
│ C  Champion             │ 0: None  │ 2: Potential│5: Committed │
│ C  Competition          │ 0: None  │ 2: Some    │ 5: Understood│
├──────────────────────────────────────────────────────────────┤
│ Overall Score: Average of all 8 dimensions                   │
│ Range: 0.0 - 5.0 (1 decimal place)                          │
└──────────────────────────────────────────────────────────────┘
```

**Additional Fields**:
- `summary`: High-level assessment of the call
- `key_gaps`: Critical missing elements
- `positive_indicators`: Strengths to leverage
- `coaching_focus`: Specific areas for rep improvement

---

### TRIAL (Trial Health) - 5 Dimensions

**Goal**: Assess trial health and likelihood to convert

```
┌──────────────────────────────────────────────────────────────┐
│ T  Technical Validation │ 0: Blockers│ 2: Some   │ 5: Working  │
│ R  Readiness & Progress │ 0: Stalled │ 2: Mixed  │ 5: On Track │
│ I  Internal Adoption    │ 0: Poor    │ 2: Moderate│5: High     │
│ A  Advocacy & Sentiment │ 0: Negative│ 2: Neutral│ 5: Positive │
│ L  Landscape/Competition│ 0: Losing  │ 2: Competing│5: Leading │
├──────────────────────────────────────────────────────────────┤
│ Overall Score: Average of all 5 dimensions                   │
│ Health: Healthy (4.0-5.0) | At Risk (2.5-3.9) | Critical (0-2.4)│
└──────────────────────────────────────────────────────────────┘
```

**Additional Fields**:
- `summary`: Trial health overview
- `key_concerns`: Issues that need addressing
- `positive_signals`: Encouraging signs
- `recommended_actions`: Next steps to improve trial

---

### CLOSE (Deal Health) - 5 Dimensions

**Goal**: Assess deal health and likelihood to close

```
┌──────────────────────────────────────────────────────────────┐
│ C  Commercial Alignment │ 0: Far Apart│ 2: Negotiating│5: Agreed│
│ L  Legal & Compliance   │ 0: Blockers │ 2: Working    │5: Met   │
│ O  Org. Consensus       │ 0: Misaligned│2: Partial    │5: Aligned│
│ S  Single-Threading Risk│ 0: One contact│2: Few       │5: Multi │
│ E  Execution Momentum   │ 0: Stalled  │ 2: Slow       │5: Active│
├──────────────────────────────────────────────────────────────┤
│ Overall Score: Average of all 5 dimensions                   │
│ Health: Healthy (4.0-5.0) | At Risk (2.5-3.9) | Critical (0-2.4)│
└──────────────────────────────────────────────────────────────┘
```

**Additional Fields**:
- `summary`: Deal health overview
- `deal_risks`: Potential blockers or concerns
- `positive_signals`: Encouraging momentum
- `recommended_actions`: Next steps to advance the deal

---

### Win/Loss Analysis (Closed)

**Goal**: Understand why we won or lost

```
┌──────────────────────────────────────────────────────────────┐
│ • Outcome: Won or Lost                                       │
│ • Primary Reasons: Why did we win/lose?                      │
│ • Stage of Decision: Where was outcome determined?           │
│ • Critical Dimensions: Which factors mattered most?          │
│ • Competitive Factor: Who we competed against                │
│ • Key Learnings: What to replicate/avoid                     │
│ • Verbatim Quotes: Supporting evidence from transcript       │
└──────────────────────────────────────────────────────────────┘
```

---

## Speaker Identification

### Challenge

Raw Gong transcripts use numeric speaker IDs:
```
[2349112610150941359]: Let's discuss your requirements.
[7726781942202217419]: We need to improve our conversion rate.
```

**Problem**: LLM doesn't know who is sales rep vs customer.

### Solution

1. **Fetch Participants**: Get participant data from Gong `/v2/calls/extensive` endpoint
   - Includes: `speakerId`, `name`, `title`, `emailAddress`, `affiliation`

2. **Store Participants**: Save to `call_participants` table
   - Links `speaker_id` to participant details

3. **Enrich Transcript**: Replace speaker IDs with meaningful labels
   ```python
   enriched_transcript = repository.enrich_transcript_with_participants(call_id, raw_transcript)
   ```

4. **Result**:
   ```
   [Sales - John]: Let's discuss your requirements.
   [Customer - Sarah]: We need to improve our conversion rate.
   ```

**Benefits**:
- LLM understands speaker roles
- Better context for evaluation
- More accurate MEDDPICC/TRIAL/CLOSE scoring

---

## Streamlit Dashboards

### Home Page

**File**: `streamlit_app/Home.py`

**Features**:
- Welcome message
- Quick stats (total accounts, calls, segments)
- Navigation to other pages

---

### Accounts Page

**File**: `streamlit_app/pages/2_accounts.py`

**Features**:

1. **Account List** (left sidebar)
   - All accounts sorted by most recent call
   - Shows: domain, stage, segment, last call date
   - Clickable to view details

2. **Account Details** (main area)
   - **Account Info**: Domain, stage, total calls, date range
   - **Customer Contacts**: All external participants (name, title, email)
   - **Call History**: List of all calls with expandable details
     - Call date, title, stage
     - Participants (internal and external)
     - Scores (MEDDPICC/TRIAL/CLOSE depending on stage)
     - Full analysis breakdown

3. **Filtering**:
   - By segment (enterprise, scale, velocity)
   - By stage (discovery, trial, negotiation, closed)

---

### Calls Page

**File**: `streamlit_app/pages/3_calls.py`

**Features**:

1. **Call List** (left sidebar)
   - All calls sorted by date
   - Shows: account domain, title, stage, date
   - Color-coded by stage

2. **Call Details** (main area)
   - **Metadata**: Date, account, sales rep, stage
   - **Participants**: Internal and external attendees
   - **Scores**: Stage-appropriate evaluation
     - MEDDPICC dimensions + analysis
     - TRIAL dimensions + health
     - CLOSE dimensions + health
     - Win/Loss analysis
   - **Transcript**: (if available/needed)

3. **Filtering**:
   - By stage
   - By sales rep
   - By date range

---

## Entry Points

### CLI: `process_calls.py`

Process calls from Gong and evaluate them.

**Usage**:
```bash
# Process recent calls (default: 30 days)
python process_calls.py

# Process with limit (testing)
python process_calls.py --limit 10

# Process specific segment
python process_calls.py --segment enterprise

# Process single call
python process_calls.py --call-id abc123

# Reset database first
python process_calls.py --reset --limit 5
```

**Flow**:
1. Load configuration from `.env`
2. Initialize Gong client, LLM client, database, repository
3. Load active sales reps from database
4. Fetch calls from Gong (last N days)
5. Process each call through pipeline
6. Print summary (processed, skipped, failed)

---

### Streamlit: `streamlit run streamlit_app/Home.py`

Launch the dashboard.

**Usage**:
```bash
# Default port (8501)
streamlit run streamlit_app/Home.py

# Custom port
streamlit run streamlit_app/Home.py --server.port 8080
```

---

## Configuration

### Environment Variables (`.env`)

```bash
# Gong API
GONG_API_URL=https://us-XXXX-api.gong.io
GONG_ACCESS_KEY=your_access_key
GONG_SECRET_KEY=your_secret_key
GONG_LOOKBACK_DAYS=30
INTERNAL_DOMAIN=yourcompany.com

# LLM (Anthropic Claude)
LLM_PROVIDER=anthropic
LLM_API_KEY=your_anthropic_key
LLM_MODEL=claude-sonnet-4-5-20250929

# Database
DB_TYPE=sqlite
SQLITE_DB_PATH=~/introspect/data/calls.db

# (Optional) PostgreSQL
DATABASE_URL=postgresql://user:pass@host:5432/introspect
```

---

## LLM Integration

### Provider: Anthropic Claude

**Models Used**:
- **Stage Classification**: Claude Sonnet 4.5 (fast, accurate)
- **Evaluations**: Claude Sonnet 4.5 (structured output)

**Why Claude**:
- Superior reasoning for nuanced sales conversations
- Structured output support (JSON mode)
- Better at following strict scoring rubrics (0/2/5)
- Extended context window (200k tokens)

### Prompt Engineering

**Structured Output**: All evaluators use JSON schema enforcement:
```python
response = llm_client.call_llm(
    prompt=transcript,
    system_message=evaluation_framework,
    response_format={"type": "json_object"},
    model_name="claude-sonnet-4-5-20250929"
)
```

**Scoring Rubric**: Explicitly defined in system prompts:
- **5**: Fully met, explicit evidence in transcript
- **2**: Partially met, some discussion but incomplete
- **0**: Not met, no evidence or explicitly missing

---

## Out-of-Order Processing

### Challenge

Calls may be processed in any order (not necessarily chronological).

### Solution

**Account State Updates**: Only update current state fields if call is newer than `last_call_date`:

```python
if account.last_call_date is None or call.call_date > account.last_call_date:
    # Update current state
    account.current_stage = call.primary_stage
    account.primary_sales_rep = call.sales_rep_email
    account.primary_segment = rep_segment
    account.last_call_date = call.call_date
```

**Historical Fields**: Always update:
- `first_call_date`: If call is older than current first
- `total_calls`: Always increment

**Benefits**:
- Can backfill historical calls without corrupting current state
- Can reprocess failed calls safely
- Account always reflects latest known state

---

## Testing

### Import Test

```bash
python test_imports.py
```

Verifies all modules import correctly.

---

### Participant Enrichment Test

```bash
python test_enriched_transcript.py [call_id]
```

Shows before/after transcript enrichment.

---

### Backfill Participants

```bash
# Backfill all existing calls
python backfill_call_participants.py --all

# Test with limit
python backfill_call_participants.py --limit 10
```

---

## Deployment

See `DEPLOYMENT_GUIDE.md` for complete deployment instructions.

**Summary**:
1. **Cloud Run**: Serverless container platform
2. **IAP**: Google Workspace authentication (no user list)
3. **Database**: SQLite + Cloud Storage OR Cloud SQL PostgreSQL
4. **Secrets**: Secret Manager for API keys

**Cost**: ~$15-30/month for 10 users

---

## Current Status

### ✅ Implemented

- Multi-stage evaluation (discovery, trial, negotiation, closed)
- Stage classification with confidence scoring
- 4 evaluation frameworks (MEDDPICC, TRIAL, CLOSE, Win/Loss)
- Speaker identification and transcript enrichment
- Normalized database with 12 tables
- Repository pattern for data access
- Call processing pipeline
- Streamlit dashboards (Home, Accounts, Calls)
- PostgreSQL migration support
- Deployment guide

### 🚧 Future Enhancements

- Account aggregation automation (currently manual via SQL)
- Stage transition detection and tracking
- Slack notifications for at-risk deals
- Rep performance analytics
- Win/loss pattern detection
- Automated coaching recommendations

---

## Best Practices

### Processing Workflow

1. **Load Sales Reps**: Add sales reps to database first
   ```bash
   python load_sales_reps.py
   ```

2. **Process Calls**: Run processing regularly
   ```bash
   # Daily cron job
   python process_calls.py --days 7
   ```

3. **View Results**: Use Streamlit dashboard
   ```bash
   streamlit run streamlit_app/Home.py
   ```

### Error Handling

- **Already Processed**: Calls are skipped automatically (checks `call_id`)
- **No Transcript**: Calls without transcripts are skipped
- **LLM Failures**: Logged but don't stop processing
- **API Rate Limits**: Implement exponential backoff

### Performance

- **Batch Processing**: Process in batches of 50 (Gong API limit)
- **Concurrent LLM Calls**: Could parallelize evaluations (not implemented)
- **Database Indexes**: Schema includes indexes on common query patterns

---

## Summary

Introspect provides end-to-end sales call analysis:

1. **Fetches** calls from Gong with participant data
2. **Enriches** transcripts with speaker names and roles
3. **Classifies** stage automatically
4. **Evaluates** using stage-appropriate framework
5. **Stores** results in normalized database
6. **Visualizes** insights in Streamlit dashboards

**Result**: Actionable, quantitative insights into deal qualification, trial health, and close readiness - with full speaker context for accurate analysis.
