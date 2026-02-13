# Introspect Frontend Specification

**Version:** 1.0
**Date:** 2026-02-12
**Purpose:** Sales coaching and account qualification dashboard

---

## 1. Overview

### 1.1 Goals
- Enable effective sales coaching at team and individual rep level
- Identify strong vs weak account opportunities based on MEDDPICC discovery
- Help sales team qualify deals faster and focus on high-quality opportunities
- Track improvement over time

### 1.2 Primary Users
- Sales Manager (coaching the team)
- Individual Sales Reps (self-coaching)
- Sales Ops (tracking team performance)

### 1.3 Core Use Cases
1. **Team Coaching:** Identify team-wide weaknesses in MEDDPICC discovery
2. **Individual Coaching:** Deep dive into specific rep performance
3. **Account Qualification:** Identify which accounts have strong/weak discovery
4. **Trend Tracking:** Monitor improvement over time

---

## 2. Technical Architecture

### 2.1 Tech Stack
- **Framework:** Streamlit 1.31+
- **Charts:** Plotly Express + Plotly Graph Objects
- **Database:** SQLite (existing `./data/calls.db`)
- **Data Access:** Reuse existing `src/sqlite_repository.py`
- **Python:** 3.9+

### 2.2 Project Structure
```
streamlit_app/
├── app.py                          # Main entry point (redirect to Coaching)
├── pages/
│   ├── 1_🎓_Team_Coaching.py      # Team coaching dashboard
│   ├── 2_👤_Rep_Coaching.py       # Individual rep view
│   ├── 3_🏢_Account_Qualification.py  # Account dashboard
│   └── 4_⚙️_Settings.py           # Filters and config
├── utils/
│   ├── db_queries.py               # Database query functions
│   ├── metrics.py                  # Metric calculations
│   ├── charts.py                   # Chart builders
│   └── styling.py                  # Colors, themes, formatters
├── .streamlit/
│   └── config.toml                 # Streamlit config
└── requirements_ui.txt             # UI-specific dependencies
```

### 2.3 Data Flow
```
SQLite DB (./data/calls.db)
    ↓
SQLiteCallRepository (existing from src/)
    ↓ Returns AccountRecord objects
db_queries.py (filtering, aggregation in Python)
    ↓
metrics.py (calculate derived metrics)
    ↓
charts.py (build Plotly visualizations)
    ↓
Streamlit UI (pages/)
```

**Data Models** (already exist in `src/models.py`):
- `AccountRecord`: domain, created_at, updated_at, calls[], overall_meddpicc
- `AccountCall`: call_id, call_date, sales_rep, external_participants, meddpicc_scores, meddpicc_summary, analysis_notes
- `MEDDPICCScores`: 8 dimensions (0-5) + overall_score
- `AnalysisNotes`: Detailed reasoning per dimension

### 2.4 Current Database State
As of 2026-02-12:
- **503 evaluated calls** (discovery + non-discovery)
- **223 accounts** (domains with discovery calls)
- All calls stored as JSON within accounts table
- Rejection reasons available for non-discovery calls

---

## 3. Data Model & Queries

### 3.1 Database Schema (Actual)

**Table: accounts**
```sql
CREATE TABLE accounts (
    domain TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,           -- ISO datetime
    updated_at TEXT NOT NULL,           -- ISO datetime
    calls TEXT NOT NULL,                -- JSON array of AccountCall objects
    overall_meddpicc TEXT NOT NULL      -- JSON object of MEDDPICCScores
)
```

**Table: evaluated_calls**
```sql
CREATE TABLE evaluated_calls (
    call_id TEXT PRIMARY KEY,
    evaluated_at TEXT NOT NULL,         -- ISO datetime
    is_discovery INTEGER NOT NULL,      -- 1 = discovery, 0 = not discovery
    reason TEXT                         -- Rejection reason (only for non-discovery)
)
```

**Important Notes:**
- `calls` column stores a JSON array of call objects with full details
- Each call in the array contains: call_id, call_date, sales_rep, external_participants, meddpicc_scores, meddpicc_summary, analysis_notes
- `overall_meddpicc` is the max score per dimension across all calls for that account
- Date filtering must be done in Python after loading data (dates are in JSON)
- No direct SQL joins possible - must parse JSON arrays

### 3.2 Required Database Query Functions

**Important:** Use existing `SQLiteCallRepository` from `src/sqlite_repository.py` where possible.

#### Query 1: Get all accounts with optional filtering
```python
async def get_all_accounts_filtered(
    repository: SQLiteCallRepository,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    min_calls: Optional[int] = None,
    max_score: Optional[float] = None
) -> List[AccountRecord]:
    """
    Get all accounts with optional filters applied in Python.

    Args:
        repository: SQLiteCallRepository instance
        date_from: Filter calls on/after this date
        date_to: Filter calls on/before this date
        min_calls: Only return accounts with at least this many calls
        max_score: Only return accounts with score <= this value

    Returns:
        List[AccountRecord] with filtered calls

    Note: Date filtering is applied to calls within each account,
          but account is included if it has at least one call in range.
    """
    # Get all accounts from DB
    all_accounts = await repository.get_all_accounts()

    filtered_accounts = []
    for account in all_accounts:
        # Filter calls by date range
        filtered_calls = account.calls
        if date_from:
            filtered_calls = [c for c in filtered_calls if c.call_date >= date_from]
        if date_to:
            filtered_calls = [c for c in filtered_calls if c.call_date <= date_to]

        # Skip if no calls in date range
        if not filtered_calls:
            continue

        # Apply min_calls filter
        if min_calls and len(filtered_calls) < min_calls:
            continue

        # Apply max_score filter
        if max_score and account.overall_meddpicc.overall_score > max_score:
            continue

        # Create filtered account (with recalculated overall_meddpicc if date filtered)
        if date_from or date_to:
            # Recalculate overall MEDDPICC from filtered calls
            filtered_account = AccountRecord(
                domain=account.domain,
                created_at=account.created_at,
                updated_at=account.updated_at,
                calls=filtered_calls,
                overall_meddpicc=repository._calculate_overall_meddpicc(filtered_calls)
            )
            filtered_accounts.append(filtered_account)
        else:
            filtered_accounts.append(account)

    return filtered_accounts
```

#### Query 2: Get all calls by sales rep
```python
def get_calls_by_rep(
    accounts: List[AccountRecord],
    rep_email: str
) -> List[AccountCall]:
    """
    Extract all calls for a specific sales rep from accounts.

    Args:
        accounts: List of AccountRecord objects
        rep_email: Sales rep email to filter by

    Returns:
        List[AccountCall] for this rep, sorted by date descending
    """
    rep_calls = []
    for account in accounts:
        rep_calls.extend([
            call for call in account.calls
            if call.sales_rep == rep_email
        ])

    # Sort by date, most recent first
    rep_calls.sort(key=lambda c: c.call_date, reverse=True)
    return rep_calls
```

#### Query 3: Get team statistics
```python
def get_team_stats(accounts: List[AccountRecord]) -> Dict[str, Any]:
    """
    Calculate team-wide statistics from accounts.

    Args:
        accounts: List of AccountRecord objects

    Returns:
        Dict with team statistics:
        - total_discovery_calls: int
        - unique_reps: int
        - unique_accounts: int
        - avg_overall_score: float
        - avg_scores_by_dimension: Dict[str, float]
    """
    # Collect all calls
    all_calls = []
    all_reps = set()

    for account in accounts:
        all_calls.extend(account.calls)
        for call in account.calls:
            all_reps.add(call.sales_rep)

    if not all_calls:
        return {
            'total_discovery_calls': 0,
            'unique_reps': 0,
            'unique_accounts': 0,
            'avg_overall_score': 0.0,
            'avg_scores_by_dimension': {}
        }

    # Calculate averages
    dimensions = ['metrics', 'economic_buyer', 'decision_criteria',
                  'decision_process', 'paper_process', 'identify_pain',
                  'champion', 'competition']

    avg_scores = {}
    for dim in dimensions:
        scores = [getattr(call.meddpicc_scores, dim) for call in all_calls]
        avg_scores[dim] = sum(scores) / len(scores)

    overall_scores = [call.meddpicc_scores.overall_score for call in all_calls]

    return {
        'total_discovery_calls': len(all_calls),
        'unique_reps': len(all_reps),
        'unique_accounts': len(accounts),
        'avg_overall_score': sum(overall_scores) / len(overall_scores),
        'avg_scores_by_dimension': avg_scores
    }
```

#### Query 4: Get rep comparison data
```python
def get_rep_comparison(accounts: List[AccountRecord]) -> List[Dict[str, Any]]:
    """
    Get per-rep statistics for comparison.

    Args:
        accounts: List of AccountRecord objects

    Returns:
        List[Dict] with one entry per rep:
        - rep_email: str
        - total_calls: int
        - avg_overall_score: float
        - avg_scores_by_dimension: Dict[str, float]
    """
    # Group calls by rep
    calls_by_rep = {}
    for account in accounts:
        for call in account.calls:
            if call.sales_rep not in calls_by_rep:
                calls_by_rep[call.sales_rep] = []
            calls_by_rep[call.sales_rep].append(call)

    # Calculate stats per rep
    rep_stats = []
    dimensions = ['metrics', 'economic_buyer', 'decision_criteria',
                  'decision_process', 'paper_process', 'identify_pain',
                  'champion', 'competition']

    for rep_email, calls in calls_by_rep.items():
        # Calculate dimension averages
        avg_scores = {}
        for dim in dimensions:
            scores = [getattr(call.meddpicc_scores, dim) for call in calls]
            avg_scores[dim] = sum(scores) / len(scores)

        # Overall average
        overall_scores = [call.meddpicc_scores.overall_score for call in calls]
        avg_overall = sum(overall_scores) / len(overall_scores)

        rep_stats.append({
            'rep_email': rep_email,
            'total_calls': len(calls),
            'avg_overall_score': avg_overall,
            'avg_scores_by_dimension': avg_scores
        })

    # Sort by overall score descending
    rep_stats.sort(key=lambda r: r['avg_overall_score'], reverse=True)
    return rep_stats
```

#### Query 5: Get time series data
```python
def get_time_series(
    accounts: List[AccountRecord],
    group_by: str = 'week'
) -> List[Dict[str, Any]]:
    """
    Get time series data grouped by period.

    Args:
        accounts: List of AccountRecord objects
        group_by: 'day', 'week', or 'month'

    Returns:
        List[Dict] with one entry per period:
        - period: str (e.g., "2026-W03" for week, "2026-01-15" for day)
        - total_calls: int
        - avg_overall_score: float
        - avg_scores_by_dimension: Dict[str, float]
    """
    from collections import defaultdict

    # Collect all calls
    all_calls = []
    for account in accounts:
        all_calls.extend(account.calls)

    # Group calls by period
    calls_by_period = defaultdict(list)

    for call in all_calls:
        if group_by == 'day':
            period = call.call_date.strftime('%Y-%m-%d')
        elif group_by == 'week':
            period = call.call_date.strftime('%Y-W%U')
        elif group_by == 'month':
            period = call.call_date.strftime('%Y-%m')
        else:
            raise ValueError(f"Invalid group_by: {group_by}")

        calls_by_period[period].append(call)

    # Calculate stats per period
    dimensions = ['metrics', 'economic_buyer', 'decision_criteria',
                  'decision_process', 'paper_process', 'identify_pain',
                  'champion', 'competition']

    time_series = []
    for period, calls in sorted(calls_by_period.items()):
        # Calculate dimension averages
        avg_scores = {}
        for dim in dimensions:
            scores = [getattr(call.meddpicc_scores, dim) for call in calls]
            avg_scores[dim] = sum(scores) / len(scores)

        # Overall average
        overall_scores = [call.meddpicc_scores.overall_score for call in calls]

        time_series.append({
            'period': period,
            'total_calls': len(calls),
            'avg_overall_score': sum(overall_scores) / len(overall_scores),
            'avg_scores_by_dimension': avg_scores
        })

    return time_series
```

#### Query 6: Get evaluated calls statistics
```python
async def get_evaluated_calls_stats(
    repository: SQLiteCallRepository
) -> Dict[str, Any]:
    """
    Get statistics from evaluated_calls table.

    Args:
        repository: SQLiteCallRepository instance

    Returns:
        Dict with:
        - total_evaluated: int
        - total_discovery: int
        - total_non_discovery: int
        - rejection_reasons: List[Tuple[str, int]] (reason, count)
    """
    cursor = repository.conn.execute(
        "SELECT is_discovery, reason FROM evaluated_calls"
    )

    results = cursor.fetchall()

    discovery_count = sum(1 for r in results if r[0] == 1)
    non_discovery_count = sum(1 for r in results if r[0] == 0)

    # Count rejection reasons
    from collections import Counter
    reasons = [r[1] for r in results if r[0] == 0 and r[1]]
    reason_counts = Counter(reasons).most_common()

    return {
        'total_evaluated': len(results),
        'total_discovery': discovery_count,
        'total_non_discovery': non_discovery_count,
        'rejection_reasons': reason_counts
    }
```

#### Query 7: Get account red flags
```python
def get_account_red_flags(
    accounts: List[AccountRecord],
    min_calls: int = 3,
    max_score: float = 3.0
) -> List[AccountRecord]:
    """
    Get accounts that are red flags (weak after multiple calls).

    Args:
        accounts: List of AccountRecord objects
        min_calls: Minimum calls to be considered
        max_score: Maximum score to be considered weak

    Returns:
        List[AccountRecord] that are red flags
    """
    red_flags = []
    for account in accounts:
        if (len(account.calls) >= min_calls and
            account.overall_meddpicc.overall_score <= max_score):
            red_flags.append(account)

    # Sort by score (lowest first)
    red_flags.sort(key=lambda a: a.overall_meddpicc.overall_score)
    return red_flags
```

### 3.2 Derived Metrics

#### Team Level
```python
# Dimension averages
avg_metrics = avg(all_calls.meddpicc_scores.metrics)
avg_economic_buyer = avg(all_calls.meddpicc_scores.economic_buyer)
# ... for all 8 dimensions

# Team strengths (top 3 dimensions)
strengths = sorted(dimension_averages, reverse=True)[:3]

# Team weaknesses (bottom 3 dimensions)
weaknesses = sorted(dimension_averages)[:3]

# Improvement tracking (compare to previous period)
improvement = current_period_avg - previous_period_avg
```

#### Rep Level
```python
# Rep vs team comparison
rep_vs_team = {
    dimension: rep_avg - team_avg
    for dimension in MEDDPICC_DIMENSIONS
}

# Rep ranking
rep_rank = position in sorted list of reps by overall_score

# Rep trend (last N weeks)
rep_trend = linear_regression(weekly_scores)
```

#### Account Level
```python
# Account qualification status
if overall_score >= 4.0:
    status = "STRONG"
elif overall_score >= 2.5:
    status = "MODERATE"
else:
    status = "WEAK"

# Account red flags
red_flags = []
if num_calls >= 3 and overall_score < 3.0:
    red_flags.append("Multiple calls but weak qualification")
if num_calls >= 3 and economic_buyer_score < 3:
    red_flags.append("No economic buyer access")
if num_calls >= 2 and score_trend < 0:
    red_flags.append("Score declining")

# Dimension gaps (< 3 on any dimension)
gaps = [dim for dim, score in dimensions.items() if score < 3]
```

---

## 4. Page Specifications

### 4.1 Page 1: Team Coaching Dashboard

**Route:** `/Team_Coaching` (default home page)

#### 4.1.1 Layout
```
┌────────────────────────────────────────────────────┐
│ 🎓 Team Discovery Coaching Dashboard              │
├────────────────────────────────────────────────────┤
│ Filters: [Date Range] [▼ Last 30 days]            │
├────────────────────────────────────────────────────┤
│                                                    │
│ ┌──────────────────┐  ┌──────────────────────┐  │
│ │ 📊 Total Calls   │  │ 🎯 Avg MEDDPICC      │  │
│ │      45          │  │      3.4 / 5.0       │  │
│ └──────────────────┘  └──────────────────────┘  │
│ ┌──────────────────┐  ┌──────────────────────┐  │
│ │ 👥 Active Reps   │  │ 🏢 Accounts          │  │
│ │      5           │  │      23              │  │
│ └──────────────────┘  └──────────────────────┘  │
│                                                    │
├────────────────────────────────────────────────────┤
│ TEAM STRENGTHS & WEAKNESSES                        │
├────────────────────────────────────────────────────┤
│                                                    │
│ 🟢 WHERE WE'RE STRONG        🔴 WHERE WE'RE WEAK  │
│ ✓ Pain Ident.    4.2         ⚠ Econ Buyer   2.1  │
│ ✓ Metrics        3.9         ⚠ Paper Proc   2.3  │
│ ✓ Champion       3.7         ⚠ Competition  2.8  │
│                                                    │
├────────────────────────────────────────────────────┤
│ MEDDPICC HEATMAP (Rep x Dimension)                 │
├────────────────────────────────────────────────────┤
│                                                    │
│ [Plotly Heatmap showing all reps x 8 dimensions]  │
│ - Rows: Rep names                                  │
│ - Columns: M, E, DC, DP, PP, IP, CH, CO, Overall  │
│ - Color scale: Red (0-2), Yellow (2-4), Green (4-5)│
│ - Hover: Rep name, dimension, score, # calls       │
│ - Click: Navigate to rep detail                    │
│                                                    │
├────────────────────────────────────────────────────┤
│ 🎯 TOP COACHING PRIORITIES                         │
├────────────────────────────────────────────────────┤
│                                                    │
│ 1. Economic Buyer Access (2.1 avg - Critical)     │
│    • Only 3/45 calls had C-level participation    │
│    • Reps meeting with mid-level stakeholders     │
│    📞 Best example: Alice's "Acme" call (EB: 5)   │
│       [View Call Button]                           │
│                                                    │
│ 2. Paper Process Discovery (2.3 avg - Critical)   │
│    • 89% of calls scored 0-2 on this dimension    │
│    • Reps not asking about legal/procurement      │
│    📝 Action: Add to discovery template            │
│                                                    │
│ 3. Competition (2.8 avg - Needs Work)             │
│    • Surface-level questions only                  │
│    • Not digging into evaluation criteria         │
│    📝 Action: Role-play competitive discovery      │
│                                                    │
├────────────────────────────────────────────────────┤
│ 📈 TEAM IMPROVEMENT TRACKING                       │
├────────────────────────────────────────────────────┤
│                                                    │
│ [Line Chart: Weekly avg scores over time]         │
│ - Overall score trend line                         │
│ - Option to toggle individual dimensions           │
│ - Show comparison to previous period               │
│                                                    │
├────────────────────────────────────────────────────┤
│ 💡 EXAMPLE CALLS FOR TRAINING                      │
├────────────────────────────────────────────────────┤
│                                                    │
│ 🟢 Best Overall Call (4.5)                         │
│    Acme Corp - Alice Smith - Jan 22, 2026         │
│    [View in Gong] [Use in Training]               │
│                                                    │
│ 🟢 Best Economic Buyer Discovery (5.0)             │
│    Beta Inc - Alice Smith - Jan 20, 2026          │
│    [View in Gong] [Share Example]                 │
│                                                    │
│ 🔴 Common Mistakes (1.8)                           │
│    Gamma LLC - Carol Chen - Jan 18, 2026          │
│    [View for Coaching] [Anonymous Case Study]     │
│                                                    │
└────────────────────────────────────────────────────┘
```

#### 4.1.2 Components

**Component: Date Range Filter**
- Sidebar filter
- Presets: Last 7 days, Last 30 days, Last 90 days, All time, Custom range
- Default: Last 30 days
- Updates all metrics and charts on change

**Component: Metric Cards**
- 2x2 grid of key metrics
- Large number with label
- Optional delta vs previous period (e.g., "+5" in green)

**Component: Strengths/Weaknesses Cards**
- Side-by-side display
- Top 3 dimensions each
- Show dimension name and average score
- Color-coded: Green for strengths, Red for weaknesses

**Component: MEDDPICC Heatmap**
- Plotly heatmap
- Interactive hover tooltips
- Click to navigate to rep detail page
- Color scale: Red (0-2) → Yellow (2-4) → Green (4-5)
- X-axis: MEDDPICC dimensions + Overall
- Y-axis: Rep names (sorted by overall score, descending)

**Component: Coaching Priorities**
- Expandable sections (up to 5)
- Auto-generated based on weakest dimensions
- Include:
  - Dimension name and average score
  - Number/percentage of weak calls
  - Specific observation
  - Link to best example call
  - Suggested action item
- Prioritize by: (1) Lowest score, (2) Highest variance across reps

**Component: Improvement Tracking Chart**
- Plotly line chart
- X-axis: Time periods (weeks or months)
- Y-axis: Average score
- Lines: Overall + each MEDDPICC dimension (toggle on/off)
- Show trend direction (↗ improving, → flat, ↘ declining)

**Component: Example Calls Table**
- Show 3-5 notable calls:
  - Best overall
  - Best per key dimension (if significantly better than avg)
  - Worst/common mistakes (for coaching)
- Each row: Score, Account, Rep, Date, Link to Gong
- "View in Gong" button (opens gong_link)
- Optional: "Use in Training" button (copies details to clipboard)

---

### 4.2 Page 2: Rep Coaching Dashboard

**Route:** `/Rep_Coaching`

#### 4.2.1 Layout
```
┌────────────────────────────────────────────────────┐
│ 👤 Individual Rep Coaching                         │
├────────────────────────────────────────────────────┤
│ Select Rep: [Dropdown: All Reps ▼]                │
│ Date Range: [▼ Last 30 days]                      │
├────────────────────────────────────────────────────┤
│                                                    │
│ 👤 Bob Jones                                       │
│ 18 discovery calls | Overall: 3.2 (Team: 3.4) 🟡  │
│                                                    │
├────────────────────────────────────────────────────┤
│ YOUR MEDDPICC SCORECARD                            │
├────────────────────────────────────────────────────┤
│                                                    │
│ [Horizontal Bar Chart: Rep vs Team Comparison]    │
│ - Each bar shows rep score                         │
│ - Vertical line for team average                   │
│ - Color: Green (above team), Yellow (at team),     │
│          Red (below team)                          │
│ - Dimensions sorted by delta (biggest gap first)   │
│                                                    │
│ Metrics (M)         ███░░ 3.5  (Team: 3.9) -0.4   │
│ Econ Buyer (E)      ██░░░ 2.1  (Team: 2.1) =0.0   │
│ Decision Crit (DC)  █████ 4.2  (Team: 3.6) +0.6 ✓ │
│ ...                                                │
│                                                    │
├────────────────────────────────────────────────────┤
│ 🎯 YOUR TOP 3 FOCUS AREAS                          │
├────────────────────────────────────────────────────┤
│                                                    │
│ 1. 🔴 Paper Process (1.9 avg - Your weakest)      │
│    What you're missing:                            │
│    • Legal review process                          │
│    • Procurement requirements                      │
│    • Signature authority                           │
│                                                    │
│    📝 Questions to ask:                            │
│    "Walk me through what happens after we agree    │
│     on terms..."                                   │
│    "Who needs to sign off internally?"            │
│                                                    │
│    📞 Example to study:                            │
│    Alice's "Acme Corp" call (PP: 5)               │
│    [View in Gong]                                  │
│                                                    │
│ 2. 🟡 Champion Building (3.0 avg)                  │
│    You identify champions but not testing:         │
│    • Willingness to sell internally                │
│    • Influence with economic buyer                 │
│    • Ability to multi-thread                       │
│                                                    │
│    📞 Your best champion call:                     │
│    "Beta Inc" (CH: 4) - Jan 15                    │
│    [Review This One]                               │
│                                                    │
│ 3. 🟡 Competition (2.5 avg)                        │
│    [Similar structure...]                          │
│                                                    │
├────────────────────────────────────────────────────┤
│ 📈 YOUR PROGRESS (Last 60 days)                    │
├────────────────────────────────────────────────────┤
│                                                    │
│ [Line Chart: Rep's score over time]               │
│ - Overall score + toggleable dimensions            │
│ - Show weekly rolling average                      │
│ - Annotate significant events/improvements         │
│                                                    │
│ Recent improvements:                               │
│ ✓ Decision Criteria: 3.1 → 4.2 (+1.1) 🎉         │
│ ✓ Pain: 3.5 → 4.1 (+0.6)                         │
│ → Paper Process: 1.8 → 1.9 (+0.1) Still needs work│
│                                                    │
├────────────────────────────────────────────────────┤
│ 📋 YOUR RECENT CALLS                               │
├────────────────────────────────────────────────────┤
│                                                    │
│ [Interactive Table]                                │
│ Columns: Date, Account, Overall Score, Strengths,  │
│          Gaps, Gong Link                           │
│ - Sortable by any column                           │
│ - Color-coded scores                               │
│ - Click row to expand details                      │
│                                                    │
│ Expanded row shows:                                │
│ - Full MEDDPICC breakdown                          │
│ - Summary                                          │
│ - Analysis notes per dimension                     │
│                                                    │
├────────────────────────────────────────────────────┤
│ 💪 YOUR STRENGTHS                                  │
├────────────────────────────────────────────────────┤
│                                                    │
│ ✓ Decision Criteria (4.2) - Top on the team!      │
│   You're excellent at uncovering evaluation        │
│   criteria                                         │
│                                                    │
│ ✓ Pain Discovery (4.1) - Above team average       │
│   You dig deep on business pain points             │
│                                                    │
│ 💡 Consider coaching Carol on Decision Criteria    │
│                                                    │
└────────────────────────────────────────────────────┘
```

#### 4.2.2 Components

**Component: Rep Selector**
- Sidebar dropdown
- List all reps alphabetically
- Show call count next to each rep name
- Persist selection across page reloads (session state)

**Component: Rep Header Card**
- Rep name and email
- Total calls in selected period
- Overall score with team comparison
- Status indicator (🟢🟡🔴)

**Component: Scorecard Chart**
- Horizontal bar chart (Plotly)
- Each bar = rep score for that dimension
- Vertical line overlay = team average
- Bars colored by performance:
  - Green: ≥ 0.3 above team
  - Yellow: -0.3 to +0.3 from team
  - Red: > 0.3 below team
- Sort dimensions by delta (biggest gaps at top)
- Hover: Show exact scores and # of calls

**Component: Focus Areas**
- Auto-generated coaching recommendations
- Logic:
  1. Identify rep's weakest dimensions (score < 3 OR significantly below team)
  2. For top 3 weaknesses, generate coaching content:
     - What they're missing (based on analysis_notes from low-scoring calls)
     - Specific questions to ask (pre-written templates)
     - Best example call to study (highest scoring call for that dimension, team-wide)
     - Rep's best call for that dimension (if any)
- Expandable/collapsible sections

**Component: Progress Chart**
- Line chart showing rep's scores over time
- Group by week (rolling 7-day average)
- Multiple lines (overall + dimensions)
- Dimension lines toggleable
- Annotations for significant changes
- Below chart: Text summary of improvements/regressions

**Component: Recent Calls Table**
- Sortable, filterable table
- Click row to expand inline details
- Expanded view shows:
  - Full MEDDPICC score breakdown (8 dimensions)
  - Overall summary
  - Key analysis notes
  - Link to Gong
- Export to CSV option

**Component: Strengths Card**
- Show rep's top 2-3 dimensions (significantly above team)
- Brief explanation of why it's a strength
- Suggestion for peer coaching (if applicable)

---

### 4.3 Page 3: Account Qualification Dashboard

**Route:** `/Account_Qualification`

#### 4.3.1 Layout
```
┌────────────────────────────────────────────────────┐
│ 🏢 Account Qualification Dashboard                 │
├────────────────────────────────────────────────────┤
│ Date Range: [▼ Last 30 days]                      │
│ Filters: [All ▼] [Strong 🟢] [Weak 🔴] [Stalled ⚠️]│
├────────────────────────────────────────────────────┤
│                                                    │
│ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐│
│ │ Total        │ │ Strong (4+)  │ │ Weak (<2.5) ││
│ │   52         │ │   12 (23%)   │ │   8 (15%)   ││
│ └──────────────┘ └──────────────┘ └─────────────┘│
│                                                    │
├────────────────────────────────────────────────────┤
│ 🔴 RED FLAGS - Need Attention (8 accounts)         │
├────────────────────────────────────────────────────┤
│                                                    │
│ [Sortable Table]                                   │
│ Account    Calls  Score  Last Call  Red Flags      │
│ ─────────────────────────────────────────────────  │
│ gamma.com    4    2.1🔴  Jan 20     • No EB after  │
│                                       4 calls      │
│                                     • PP still 0   │
│                          [View Details]            │
│                                                    │
│ delta.io     3    2.3🔴  Jan 18     • No champion  │
│                                     • Pain ↘       │
│                          [View Details]            │
│ ...                                                │
│                                                    │
├────────────────────────────────────────────────────┤
│ 🟢 STRONG QUAL - Keep Pushing (12 accounts)        │
├────────────────────────────────────────────────────┤
│                                                    │
│ [Sortable Table]                                   │
│ Account     Calls  Score  Last Call  Strengths     │
│ ─────────────────────────────────────────────────  │
│ acme.com      3    4.2🟢  Jan 22     All dims 4+   │
│                                      CFO engaged   │
│                          [View Details]            │
│                                                    │
│ beta.io       2    4.0🟢  Jan 20     Strong champ  │
│                                      Good pain     │
│                          [View Details]            │
│ ...                                                │
│                                                    │
├────────────────────────────────────────────────────┤
│ 🟡 MODERATE - Needs More Discovery (32 accounts)   │
├────────────────────────────────────────────────────┤
│                                                    │
│ [Sortable Table - Collapsed by default]           │
│ [Expand to show all]                               │
│                                                    │
└────────────────────────────────────────────────────┘
```

#### 4.3.2 Account Detail Modal/Page
```
┌────────────────────────────────────────────────────┐
│ 🏢 Acme Corp (acme.com)                            │
│ Overall MEDDPICC: 4.2 🟢 STRONG QUALIFICATION      │
├────────────────────────────────────────────────────┤
│                                                    │
│ QUALIFICATION STATUS                               │
│                                                    │
│ [Horizontal Bar Chart: MEDDPICC Coverage]         │
│ M  [█████] 5.0  ✓ $2M annual savings target       │
│ E  [█████] 5.0  ✓ CFO engaged, has budget         │
│ DC [████░] 4.0  ✓ 8 criteria, we score well       │
│ DP [████░] 4.0  ✓ 3-stage eval, in stage 2        │
│ PP [███░░] 3.0  ⚠ Legal 2-week review unclear     │
│ IP [█████] 5.0  ✓ Downtime costing $50K/mo        │
│ CH [█████] 5.0  ✓ VP Ops = strong champion        │
│ CO [████░] 4.0  ✓ vs Status quo + Competitor X    │
│                                                    │
├────────────────────────────────────────────────────┤
│ 🎯 GAPS TO CLOSE                                   │
├────────────────────────────────────────────────────┤
│                                                    │
│ 1. Paper Process (Score: 3)                       │
│    ⚠️  Legal review timeline unclear               │
│    ⚠️  Procurement requirements unknown            │
│                                                    │
│    Next call action items:                         │
│    → Ask: "Walk me through legal review process?" │
│    → Ask: "What procurement hoops to jump through?"│
│                                                    │
├────────────────────────────────────────────────────┤
│ 📊 DISCOVERY EVOLUTION (3 calls)                   │
├────────────────────────────────────────────────────┤
│                                                    │
│ [Line Chart: Each dimension across calls]         │
│ - X-axis: Call dates                               │
│ - Y-axis: Score (0-5)                              │
│ - 8 lines (one per dimension)                      │
│ - Annotations for key insights                     │
│                                                    │
│ Call 1 (Jan 5):  Overall 3.2  Initial discovery   │
│ Call 2 (Jan 15): Overall 3.8  ↗ Champion emerged  │
│ Call 3 (Jan 22): Overall 4.2  ↗ Met CFO (EB)      │
│                                                    │
│ Improving: ✓ E(2→5), CH(3→5), IP(4→5)            │
│ Flat: → PP(2→3→3) ⚠️ Needs work                   │
│                                                    │
├────────────────────────────────────────────────────┤
│ 📞 CALL HISTORY                                    │
├────────────────────────────────────────────────────┤
│                                                    │
│ [Expandable Call Cards]                            │
│                                                    │
│ ▼ Jan 22 - Executive Meeting (4.2) - Alice Smith  │
│   → Met with CFO, confirmed budget and pain       │
│   → Uncovered 8 decision criteria                  │
│   → Still vague on paper process                   │
│   [View Full MEDDPICC] [View in Gong]             │
│                                                    │
│ ▼ Jan 15 - Follow-up (3.8) - Bob Jones            │
│   → VP Ops becoming strong champion                │
│   → Clarified decision process (3 stages)          │
│   [View Full MEDDPICC] [View in Gong]             │
│                                                    │
│ ▼ Jan 5 - Initial Discovery (3.2) - Bob Jones     │
│   → Good pain identification                       │
│   → Only met with director-level                   │
│   [View Full MEDDPICC] [View in Gong]             │
│                                                    │
├────────────────────────────────────────────────────┤
│ 💡 RECOMMENDED NEXT STEPS                          │
├────────────────────────────────────────────────────┤
│                                                    │
│ 1. Schedule call with Legal/Procurement            │
│    (Address Paper Process gap)                     │
│                                                    │
│ 2. Have champion multi-thread to other stakeholders│
│                                                    │
│ 3. Prep competitive positioning doc based on their │
│    criteria                                        │
│                                                    │
│ ✅ This is a HIGH QUALITY opportunity - prioritize!│
│                                                    │
└────────────────────────────────────────────────────┘
```

#### 4.3.3 Components

**Component: Account Summary Cards**
- 3 metric cards showing counts and percentages
- Total accounts, Strong (4+), Weak (<2.5)
- Click to filter list

**Component: Account List Tables**
- Three separate tables: Red Flags, Strong, Moderate
- Each table: Sortable by any column
- Default sort: Score (ascending for red flags, descending for strong)
- Columns:
  - Account domain
  - # Calls
  - Overall score (colored badge)
  - Last call date
  - Key insight (1-2 bullet points)
  - "View Details" button
- Red Flags table: Auto-generate red flag reasons
- Strong table: Auto-generate strengths
- Moderate table: Show next steps

**Component: Account Detail View**
- Opens in modal or expander
- MEDDPICC Coverage: Horizontal bar chart
  - Bars colored by score
  - Show score value
  - Hover: Show analysis notes
- Gaps section: Auto-generated from low-scoring dimensions
  - Only show dimensions < 4
  - Suggest specific questions
- Evolution Chart: Plotly line chart
  - Show all 8 dimensions across all calls
  - Annotate significant changes
- Call History: Expandable cards
  - Most recent first
  - Show date, title, rep, score, key takeaways
  - Expand to see full MEDDPICC breakdown
- Next Steps: Auto-generated recommendations
  - Based on gaps and call history
  - Prioritize based on score and urgency

**Logic: Red Flag Detection**
```python
def detect_red_flags(account):
    flags = []

    # Multiple calls but weak qualification
    if account.num_calls >= 3 and account.overall_score < 3.0:
        flags.append("Weak qualification after multiple calls")

    # No economic buyer access
    if account.num_calls >= 2 and account.overall_meddpicc.economic_buyer < 3:
        flags.append(f"No economic buyer access after {account.num_calls} calls")

    # Critical dimension at 0
    for dim in ['economic_buyer', 'champion', 'identify_pain']:
        if getattr(account.overall_meddpicc, dim) == 0:
            flags.append(f"No {dim.replace('_', ' ')} identified")

    # Score declining
    if len(account.calls) >= 2:
        trend = calculate_trend(account.calls)
        if trend < -0.2:
            flags.append("Score declining over time")

    # Stalled (no progress)
    if len(account.calls) >= 3:
        recent_scores = [c.meddpicc_scores.overall_score for c in account.calls[-3:]]
        if max(recent_scores) - min(recent_scores) < 0.3:
            flags.append("No progress in recent calls")

    return flags
```

---

### 4.4 Page 4: Settings

**Route:** `/Settings`

#### 4.4.1 Layout
```
┌────────────────────────────────────────────────────┐
│ ⚙️  Settings & Configuration                       │
├────────────────────────────────────────────────────┤
│                                                    │
│ DATABASE                                           │
│ ─────────────────────────────────────────────────  │
│ Database path: ./data/calls.db                     │
│ Status: ✓ Connected                                │
│ Total records: 127 calls, 52 accounts             │
│                                                    │
│ [Refresh Data]                                     │
│                                                    │
├────────────────────────────────────────────────────┤
│ FILTERS & DEFAULTS                                 │
│ ─────────────────────────────────────────────────  │
│                                                    │
│ Default date range: [Dropdown: Last 30 days ▼]    │
│                                                    │
│ Score thresholds:                                  │
│ • Strong:   [4.0] and above                        │
│ • Weak:     [2.5] and below                        │
│                                                    │
│ Red flag thresholds:                               │
│ • Min calls for red flag: [3]                      │
│ • Max score for red flag: [3.0]                    │
│                                                    │
│ [Save Settings]                                    │
│                                                    │
├────────────────────────────────────────────────────┤
│ MEDDPICC DIMENSION LABELS                          │
│ ─────────────────────────────────────────────────  │
│                                                    │
│ Customize how dimensions are displayed:           │
│                                                    │
│ M  - Metrics                [Input]                │
│ E  - Economic Buyer         [Input]                │
│ DC - Decision Criteria      [Input]                │
│ DP - Decision Process       [Input]                │
│ PP - Paper Process          [Input]                │
│ IP - Identify Pain          [Input]                │
│ CH - Champion               [Input]                │
│ CO - Competition            [Input]                │
│                                                    │
│ [Reset to Defaults] [Save]                         │
│                                                    │
├────────────────────────────────────────────────────┤
│ EXPORT                                             │
│ ─────────────────────────────────────────────────  │
│                                                    │
│ Export all data to CSV:                            │
│ [Export Calls] [Export Accounts]                  │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## 5. Styling & Design System

### 5.1 Color Palette

```python
COLORS = {
    # Score-based colors
    'score_strong': '#10b981',    # Green
    'score_moderate': '#f59e0b',  # Yellow/Orange
    'score_weak': '#ef4444',      # Red

    # Semantic colors
    'success': '#10b981',
    'warning': '#f59e0b',
    'error': '#ef4444',
    'info': '#3b82f6',

    # Neutral
    'text_primary': '#1f2937',
    'text_secondary': '#6b7280',
    'background': '#ffffff',
    'border': '#e5e7eb',

    # Chart colors (for dimensions)
    'chart_palette': [
        '#3b82f6',  # Blue
        '#8b5cf6',  # Purple
        '#ec4899',  # Pink
        '#f59e0b',  # Orange
        '#10b981',  # Green
        '#06b6d4',  # Cyan
        '#6366f1',  # Indigo
        '#a855f7',  # Violet
    ]
}
```

### 5.2 Score Color Function

```python
def get_score_color(score: float) -> str:
    """Return color based on score."""
    if score >= 4.0:
        return COLORS['score_strong']
    elif score >= 2.5:
        return COLORS['score_moderate']
    else:
        return COLORS['score_weak']

def get_score_emoji(score: float) -> str:
    """Return emoji based on score."""
    if score >= 4.0:
        return "🟢"
    elif score >= 2.5:
        return "🟡"
    else:
        return "🔴"
```

### 5.3 Formatters

```python
def format_score(score: float) -> str:
    """Format score for display."""
    return f"{score:.1f}"

def format_delta(delta: float) -> str:
    """Format delta with + or - sign."""
    if delta > 0:
        return f"+{delta:.1f}"
    else:
        return f"{delta:.1f}"

def format_trend(delta: float) -> str:
    """Return trend arrow."""
    if delta > 0.2:
        return "↗"
    elif delta < -0.2:
        return "↘"
    else:
        return "→"

def format_dimension_name(key: str) -> str:
    """Convert dimension key to display name."""
    dimension_names = {
        'metrics': 'Metrics',
        'economic_buyer': 'Economic Buyer',
        'decision_criteria': 'Decision Criteria',
        'decision_process': 'Decision Process',
        'paper_process': 'Paper Process',
        'identify_pain': 'Identify Pain',
        'champion': 'Champion',
        'competition': 'Competition',
    }
    return dimension_names.get(key, key.replace('_', ' ').title())

def format_dimension_abbrev(key: str) -> str:
    """Convert dimension key to abbreviation."""
    abbrevs = {
        'metrics': 'M',
        'economic_buyer': 'E',
        'decision_criteria': 'DC',
        'decision_process': 'DP',
        'paper_process': 'PP',
        'identify_pain': 'IP',
        'champion': 'CH',
        'competition': 'CO',
    }
    return abbrevs.get(key, key[:2].upper())
```

### 5.4 Streamlit Config

`.streamlit/config.toml`:
```toml
[theme]
primaryColor = "#3b82f6"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f9fafb"
textColor = "#1f2937"
font = "sans serif"

[server]
headless = true
port = 8501
enableCORS = false
enableXsrfProtection = true

[browser]
gatherUsageStats = false
```

---

## 6. Implementation Plan

### Phase 1: Foundation (Day 1, Hours 1-4)
- [ ] Set up project structure (`streamlit_app/` directory)
- [ ] Create `utils/__init__.py`
- [ ] Create `utils/db_queries.py`:
  - Import existing `SQLiteCallRepository` from `src/`
  - Implement all filtering/aggregation functions (Query 1-7 from spec)
  - Test with actual database at `./data/calls.db`
- [ ] Create `utils/metrics.py`:
  - Red flag detection logic
  - Coaching priority generation
  - Trend calculations
- [ ] Create `utils/styling.py`:
  - Color palette and score color functions
  - All formatters (score, delta, trend, dimension names)
- [ ] Create `.streamlit/config.toml` with theme
- [ ] Create `requirements_ui.txt`

**Deliverable:** Data layer complete, can query all needed data from existing DB

### Phase 2: Team Coaching Dashboard (Day 1, Hours 5-8)
- [ ] Create `pages/1_Team_Coaching.py`
- [ ] Implement date range filter (sidebar)
- [ ] Implement metric cards (4 key stats)
- [ ] Implement strengths/weaknesses display
- [ ] Implement MEDDPICC heatmap (plotly)
- [ ] Implement coaching priorities section
- [ ] Implement improvement tracking chart

**Deliverable:** Team Coaching page fully functional

### Phase 3: Rep Coaching Dashboard (Day 2, Hours 1-4)
- [ ] Create `pages/2_Rep_Coaching.py`
- [ ] Implement rep selector (sidebar)
- [ ] Implement rep header card
- [ ] Implement scorecard comparison chart
- [ ] Implement focus areas section
- [ ] Implement progress tracking chart
- [ ] Implement recent calls table
- [ ] Implement strengths display

**Deliverable:** Rep Coaching page fully functional

### Phase 4: Account Qualification Dashboard (Day 2, Hours 5-8)
- [ ] Create `pages/3_Account_Qualification.py`
- [ ] Implement account summary cards
- [ ] Implement red flags table
- [ ] Implement strong accounts table
- [ ] Implement moderate accounts table
- [ ] Implement account detail view (modal/expander)
- [ ] Implement red flag detection logic
- [ ] Implement next steps recommendations

**Deliverable:** Account Qualification page fully functional

### Phase 5: Polish & Testing (Day 3, Hours 1-4)
- [ ] Create `pages/4_Settings.py`
- [ ] Add error handling and loading states
- [ ] Test with real data
- [ ] Fix bugs and edge cases
- [ ] Add tooltips and help text
- [ ] Performance optimization
- [ ] Create README for UI

**Deliverable:** Production-ready UI

### Phase 6: Documentation (Day 3, Hours 5-6)
- [ ] Write UI user guide
- [ ] Document how to run locally
- [ ] Create demo video/screenshots
- [ ] Update main README

**Deliverable:** Complete documentation

---

## 7. File Checklist

### New Files to Create
```
✓ FRONTEND_SPEC.md (this file)
□ streamlit_app/app.py
□ streamlit_app/pages/1_🎓_Team_Coaching.py
□ streamlit_app/pages/2_👤_Rep_Coaching.py
□ streamlit_app/pages/3_🏢_Account_Qualification.py
□ streamlit_app/pages/4_⚙️_Settings.py
□ streamlit_app/utils/__init__.py
□ streamlit_app/utils/db_queries.py
□ streamlit_app/utils/metrics.py
□ streamlit_app/utils/charts.py
□ streamlit_app/utils/styling.py
□ streamlit_app/.streamlit/config.toml
□ streamlit_app/requirements_ui.txt
□ streamlit_app/README.md
```

### Files to Modify
```
□ README.md (add UI section)
□ requirements.txt (add streamlit dependencies)
```

---

## 8. Dependencies

Add to `requirements_ui.txt`:
```
streamlit>=1.31.0
plotly>=5.18.0
pandas>=2.1.0
```

All other dependencies (anthropic, httpx, pydantic, etc.) already in main `requirements.txt`.

---

## 9. Running the UI

```bash
# From project root
cd streamlit_app
streamlit run app.py

# Opens browser at http://localhost:8501
```

---

## 10. Future Enhancements (Out of Scope for v1)

- [ ] Export to PDF reports
- [ ] Email digest scheduling
- [ ] Role-based access control
- [ ] Custom coaching templates editor
- [ ] Gong player embedded in UI
- [ ] Goals and target tracking
- [ ] Team vs team comparisons (if multi-team)
- [ ] Mobile app version
- [ ] Integration with CRM (Salesforce, HubSpot)

---

**End of Specification**

This spec is now ready for implementation. All components are defined, all queries are specified, and the implementation plan is broken down into phases.
