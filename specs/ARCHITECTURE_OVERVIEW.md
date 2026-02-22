# Architecture Overview

## 🎯 System Flow

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
│  2. Store participants (speaker identification)                 │
│  3. Enrich transcript with names/roles                          │
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
│  Participants: call_participants (speaker enrichment)            │
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
│  • Home Page: Overview & navigation                              │
│  • Accounts: Account details, contacts, call history            │
│  • Calls: Call analysis, transcripts, scores                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Code Organization

```
src/
├── core/                    🔧 Infrastructure Layer
│   ├── config.py           → Environment config
│   ├── gong_client.py      → Gong API client
│   └── llm_client.py       → Anthropic Claude client
│
├── domain/                  🎯 Business Entities
│   ├── sales_rep.py        → SalesRep model
│   ├── account.py          → Account, transitions, history
│   ├── call.py             → Call model
│   └── scores.py           → All score types
│       ├── MEDDPICCScores       (discovery)
│       ├── TrialScores          (trial)
│       ├── CloseScores          (negotiation)
│       └── WinLossAnalysis      (closed)
│
├── data/                    💾 Persistence Layer
│   ├── schema.sql          → Database schema (12 tables)
│   ├── database.py         → SQLite connection
│   ├── database_postgres.py → PostgreSQL support
│   └── repository.py       → CRUD operations
│       ├── Sales Rep operations
│       ├── Account operations
│       ├── Call operations
│       ├── Participant operations
│       ├── Score operations
│       └── Aggregation operations
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
├── Home.py                  → Dashboard home page
└── pages/
    ├── 2_accounts.py        → Account dashboard
    └── 3_calls.py           → Call analysis dashboard

scripts/
├── process_calls.py         → Main CLI entry point
├── load_sales_reps.py       → Load sales rep data
├── backfill_call_participants.py → Backfill speaker data
├── test_enriched_transcript.py   → Test transcript enrichment
├── migrate_sqlite_to_postgres.py → Database migration
└── test_imports.py          → Verify setup
```

---

## 🔄 Processing Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│ Step 1: FETCH CALL                                               │
├──────────────────────────────────────────────────────────────────┤
│ Input:  Gong call ID                                             │
│ Action: GongClient.get_call()                                    │
│ Output: {metaData, parties, transcript}                          │
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
│ LLM:    Claude Sonnet 4.5 analyzes content                       │
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
│ → Extracts speaker_id, name, email, affiliation from parties    │
│ → Saves to call_participants table                              │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 7: ENRICH TRANSCRIPT                                        │
├──────────────────────────────────────────────────────────────────┤
│ Repository.enrich_transcript_with_participants()                 │
│ → Maps speaker IDs to participant names and roles               │
│ → Replaces [2349...] with [Sales - John]                       │
│ → Replaces [7726...] with [Customer - Sarah]                   │
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
│ • Set current_stage = call.primary_stage                        │
│   (only if call is newer than last_call_date)                   │
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
│ • Participants stored, transcript enriched                      │
│ • Scores stored in database                                      │
│ • Account state updated                                          │
│ • Ready for dashboard visualization                             │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Database Schema

```
┌─────────────────┐
│   sales_reps    │
│  (PK: email)    │
└────────┬────────┘
         │
         │ FK
         │
┌────────▼────────────────┐         ┌──────────────────┐
│      accounts           │◄────────┤ calls            │
│  (PK: id)               │  FK     │ (PK: id)         │
│  domain (UNIQUE)        │         │ call_id (UNIQUE) │
│  current_stage          │         │ account_id       │
│  deal_status            │         │ sales_rep_email  │
│  first_call_date        │         │ primary_stage    │
│  last_call_date         │         │ stage_confidence │
│  total_calls            │         └────────┬─────────┘
└────────┬────────────────┘                  │
         │                                   │ FK call_id
         │ FK account_id                     │
    ┌────┼─────────────────┬─────────────────┼────────────────┬───────────────┐
    │    │                 │                 │                │               │
┌───▼────▼────────┐ ┌──────▼───────┐ ┌──────▼───────┐ ┌─────▼──────┐ ┌────▼───────────┐
│stage_transitions│ │account_rep   │ │call_meddpicc │ │call_trial  │ │call_close      │
│                 │ │_history      │ │_scores       │ │_scores     │ │_scores         │
│ from_stage      │ │              │ │              │ │            │ │                │
│ to_stage        │ │ rep_email    │ │ 8 dimensions │ │ 5 dims     │ │ 5 dims         │
│ transitioned_at │ │ first_call   │ │ (0/2/5)      │ │ (0/2/5)    │ │ (0/2/5)        │
└─────────────────┘ │ last_call    │ │ overall_score│ │ overall    │ │ overall        │
                    └──────────────┘ │ analysis...  │ │ health...  │ │ health...      │
                                     └──────────────┘ └────────────┘ └────────────────┘

                           ┌──────────────────┐
                           │call_participants │◄──── NEW
                           │                  │
                           │ call_id (FK)     │
                           │ speaker_id       │
                           │ name             │
                           │ email_address    │
                           │ title            │
                           │ affiliation      │
                           └──────────────────┘

    ┌────────────────────────┬──────────────────────┬──────────────────────┐
    │                        │                      │                      │
┌───▼──────────────┐  ┌──────▼────────────┐ ┌─────▼────────────┐ ┌──────▼─────────────┐
│account_meddpicc  │  │account_trial      │ │account_close     │ │call_win_loss      │
│_scores           │  │_health            │ │_health           │ │_analysis          │
│                  │  │                   │ │                  │ │                   │
│ (aggregated)     │  │ (latest)          │ │ (latest)         │ │ outcome           │
│ 8 dimensions     │  │ 5 dimensions      │ │ 5 dimensions     │ │ primary_reasons   │
│ based_on_calls   │  │ last_call_id      │ │ last_call_id     │ │ key_learnings     │
└──────────────────┘  └───────────────────┘ └──────────────────┘ └───────────────────┘
```

---

## 🎯 Evaluation Frameworks

### MEDDPICC (Discovery) - 8 Dimensions

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

### TRIAL (Trial Health) - 5 Dimensions

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

### CLOSE (Deal Health) - 5 Dimensions

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

### Win/Loss Analysis (Closed)

```
┌──────────────────────────────────────────────────────────────┐
│ • Outcome: Won or Lost                                       │
│ • Primary Reasons: Why?                                      │
│ • Stage of Decision: Where was outcome determined?           │
│ • Critical Dimensions: Which factors mattered most?          │
│ • Competitive Factor: Who we competed against                │
│ • Key Learnings: What to replicate/avoid                     │
│ • Verbatim Quotes: Supporting evidence                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 🚀 Usage

```bash
# Process last 30 days
python process_calls.py --days 30

# Process with limit (for testing)
python process_calls.py --days 30 --limit 5

# Process single call
python process_calls.py --call-id abc123

# Reset database and process
python process_calls.py --reset --days 7

# Custom database path
python process_calls.py --db-path custom.db

# Launch dashboard
streamlit run streamlit_app/Home.py
```

---

## 📊 Output Example

```
🔧 Initializing configuration...
🗄️  Initializing database at introspect.db...
✓ Database schema created/updated at introspect.db
🌐 Initializing Gong client...
🤖 Initializing LLM client...
⚙️  Initializing call processor...

📞 Processing calls from last 30 days...

============================================================
Processing call: 8234567890123456
============================================================
→ Fetching call data from Gong...
  Sales Rep: alice@company.com
  Customer Domain: acme.com
  Call Date: 2026-02-10

→ Classifying call stage...
  Primary Stage: discovery
  Confidence: 0.92

✓ Call created (DB ID: 1)

✓ Stored 4 participants
✓ Enriched transcript with 4 participants

→ Evaluating discovery stage...
  Overall MEDDPICC Score: 3.6
  ✓ MEDDPICC scores saved

→ Updating account state...
  ✓ Account updated (stage: discovery, calls: 1)

============================================================
✅ Call processing complete!
============================================================

📊 Database Summary:
  accounts: 1
  calls: 1
  call_participants: 4
  call_meddpicc_scores: 1
  sales_reps: 1

✅ Done!
```

---

## 🔑 Key Features

### ✅ Speaker Identification
- Stores participant data from Gong API
- Enriches transcripts with [Role - Name] labels
- LLM understands who is speaking (sales vs customer)

### ✅ Multi-Stage Evaluation
- Automatic stage classification
- Stage-appropriate frameworks
- Consistent 0/2/5 scoring

### ✅ Account-Centric Tracking
- Grouped by customer domain
- Tracks progression through stages
- Handles out-of-order processing

### ✅ Streamlit Dashboards
- Account details with customer contacts
- Call history and analysis
- Filterable by segment and stage

### ✅ Database Options
- SQLite for local development
- PostgreSQL for production
- Migration script provided

---

**Ready to analyze sales calls at scale! 🚀**

For detailed documentation, see:
- `DATABASE_SPEC.md` - Complete database documentation
- `APPLICATION_SPEC.md` - Application logic and features
- `DEPLOYMENT_GUIDE.md` - Cloud deployment instructions
