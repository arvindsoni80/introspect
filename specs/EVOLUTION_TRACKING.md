# MEDDPICC Evolution Tracking

## Overview

The system now tracks **how MEDDPICC aspects evolve** across multiple discovery calls for the same account. This allows you to:

1. **Save costs** - Already-evaluated calls are skipped (no redundant LLM calls)
2. **Track progression** - See how each MEDDPICC dimension improved across calls
3. **View reasoning** - Understand why scores changed with detailed analysis notes
4. **Safe re-runs** - The analyzer is idempotent (can be re-run without duplicating work)

## How It Works

### 1. Call Deduplication

Before analyzing a call, the system checks if it's already been evaluated:

```
✓ Call already in database → Skip LLM analysis (save cost & time)
✗ New call → Classify & score with LLM → Store in database
```

**Log Output:**
```
[1/10] Processing call...
   → Skipping call-123 - already evaluated
```

### 2. Reasoning Storage

Every discovery call stores:
- **MEDDPICC scores** (0-5 for each dimension)
- **Overall summary** (high-level assessment)
- **Analysis notes** (detailed reasoning for each dimension)

**Example:**
```json
{
  "call_id": "call-001",
  "meddpicc_scores": {
    "economic_buyer": 2,
    "champion": 3
  },
  "analysis_notes": {
    "economic_buyer": "Only spoke with director level, VP not engaged yet",
    "champion": "Bob is supportive but needs more internal influence"
  }
}
```

### 3. Evolution Tracking

When multiple calls exist for the same account, you can see:
- **Score progression** (e.g., Economic Buyer: 2 → 4)
- **Reasoning evolution** (what changed between calls)
- **Overall coverage** (max score achieved per dimension)

## Viewing Evolution

### Option 1: Standard Database Viewer
```bash
python view_db.py
```

Shows all accounts with:
- Overall MEDDPICC scores (max across calls)
- Individual call scores
- **Detailed reasoning** for each dimension
- Summary of each call

**Sample Output:**
```
1. acme.com
   ───────────────────────────────────────────
   Discovery Calls: 2

   📞 Call 1: call-001 (2025-01-15)
      Score: 3.0/5.0
      Summary: Good pain identification, needs economic buyer clarity

      MEDDPICC Breakdown:
        • Metrics [3/5]: Discussed ROI expectations
        • Economic Buyer [2/5]: Only spoke with director level
        • Champion [3/5]: Bob seems supportive
        ...

   📞 Call 2: call-002 (2025-01-20)
      Score: 3.75/5.0
      Summary: Strong progress, engaged VP level

      MEDDPICC Breakdown:
        • Metrics [4/5]: Quantified savings
        • Economic Buyer [4/5]: VP engaged ← IMPROVED!
        • Champion [4/5]: Strong champion identified ← IMPROVED!
        ...
```

### Option 2: Evolution Viewer (Multi-Call Accounts)
```bash
python view_evolution.py
```

Shows **only accounts with multiple calls** and highlights:
- Evolution table (scores across calls)
- Dimension improvements
- Reasoning progression

**Sample Output:**
```
🏢 acme.com
═══════════════════════════════════════════════════
Total Discovery Calls: 2
Date Range: 2025-01-15 → 2025-01-20

Call Date    Call ID      M   EB  DC  DP  PP  IP  CH  CO  Overall
───────────────────────────────────────────────────────────────
2025-01-15   call-001     3   2   4   3   2   5   3   2   3.00
2025-01-20   call-002     4   4   4   4   3   4   4   3   3.75
───────────────────────────────────────────────────────────────
OVERALL      (Max)        4   4   4   4   3   5   4   3   3.75

📊 Dimension Evolution:
   ✨ Metrics: 3 → 4 (improved by 1)
   ✨ Economic Buyer: 2 → 4 (improved by 2)
   • Decision Criteria: 4 (consistent)
   ✨ Paper Process: 2 → 3 (improved by 1)
   • Identify Pain: 5 → 4 (slight decrease)
   ✨ Champion: 3 → 4 (improved by 1)
   ✨ Competition: 2 → 3 (improved by 1)

💡 Economic Buyer Evolution (reasoning):
   Call 1 [2/5]: Only spoke with director level, VP not engaged yet
   Call 2 [4/5]: VP engaged, confirmed budget authority
```

## Benefits

### 1. **Cost Savings**
- **No redundant LLM calls** for already-analyzed calls
- Haiku model already optimized for cost
- Re-running the analyzer only processes new calls

**Example Savings:**
- 100 calls initially → $X in LLM costs
- Re-run with 10 new calls → Only $Y (10% of original cost)
- 90 calls skipped automatically

### 2. **MEDDPICC Coverage Insights**
- See which dimensions are weak across calls
- Track progress from initial discovery to later validation calls
- Identify gaps to address in next call

**Example Insight:**
```
Economic Buyer: 2 → 2 → 2 (stuck at low level)
→ Action: Schedule call with VP/C-level
```

### 3. **Sales Coaching**
- Review reasoning to understand rep's discovery approach
- Identify patterns in high-scoring vs low-scoring calls
- Share examples of effective discovery questioning

### 4. **Account Strategy**
- Understand deal progression at a glance
- Prioritize accounts with improving MEDDPICC coverage
- Identify stalled deals (no score improvements)

## Workflow

### Initial Run
```bash
# Analyze last 7 days of calls
python main.py --sales-reps alice@company.com --post-slack

# Output:
#   → 10 calls analyzed
#   → 5 discovery calls found
#   → All stored in database
```

### Subsequent Runs (Same Period)
```bash
# Re-run (e.g., next day to catch new calls)
python main.py --sales-reps alice@company.com --post-slack

# Output:
#   → 12 calls found
#   → 10 already evaluated (skipped)
#   → 2 new calls analyzed
#   → Only 2 LLM calls made
```

### View Evolution
```bash
# Standard view (all accounts)
python view_db.py

# Evolution view (multi-call accounts only)
python view_evolution.py
```

## Database Schema (Updated)

The `AccountCall` model now includes:

```python
class AccountCall(BaseModel):
    call_id: str
    call_date: datetime
    sales_rep: str
    external_participants: list[str]
    meddpicc_scores: MEDDPICCScores
    meddpicc_summary: Optional[str]        # NEW: High-level summary
    analysis_notes: Optional[AnalysisNotes] # NEW: Detailed reasoning
```

**Storage:**
- All fields stored as JSON in SQLite
- Reasoning preserved for historical reference
- No information loss on updates

## Use Cases

### 1. **Deal Progression Tracking**
"How is the Acme deal progressing?"
```bash
python view_evolution.py
# Shows 3 calls, EB score: 1 → 3 → 4
# Conclusion: Good progression, VP now engaged
```

### 2. **Gap Analysis**
"Which MEDDPICC dimensions are weak?"
```bash
python view_db.py
# Shows Competition: 1/5 across all calls
# Action: Schedule competitive positioning call
```

### 3. **Rep Performance**
"How effective are Alice's discovery calls?"
```bash
# Review reasoning in view_db.py
# Compare average scores vs other reps
# Identify coaching opportunities
```

### 4. **Cost Control**
"Avoid re-analyzing historical calls"
```bash
# System automatically skips analyzed calls
# Safe to re-run for new calls only
# Predictable LLM costs
```

## Technical Details

### Call Existence Check
```python
# In analyzer.py
if self.repository and await self.repository.call_exists(call_id):
    log("Skipping - already evaluated")
    continue
```

### Reasoning Storage
```python
# In sqlite_repository.py
new_call = AccountCall(
    call_id=call_analysis.call_id,
    meddpicc_scores=call_analysis.meddpicc_scores,
    meddpicc_summary=call_analysis.meddpicc_summary,  # Stored
    analysis_notes=call_analysis.analysis_notes,      # Stored
)
```

### Evolution Query
```python
# Get account with all calls
account = await repo.get_account("acme.com")

# Each call has full reasoning
for call in account.calls:
    print(call.analysis_notes.economic_buyer)
    # "Only spoke with director level"
```

## Future Enhancements

- **Trend charts**: Visualize score progression over time
- **Alert on stagnation**: Notify if scores don't improve after N calls
- **Coaching recommendations**: Auto-suggest focus areas based on gaps
- **Export to CRM**: Push evolution data to Salesforce/HubSpot
