# UI Specification

## Overview

This document defines the user interface for the Introspect sales analytics dashboard. It focuses on what each page should show, how users interact with it, and what questions it answers.

---

## Global Sidebar Filters

All pages share a common sidebar with these filters:

### 1. Date Range
**Type**: Radio buttons or segmented control

**Options**:
- Last 7 days (week view)
- Last 30 days (month view)
- Last 90 days (quarter view)

**Default**: Last 30 days

**Behavior**: Applies to all data and charts on current page

---

### 2. Segment Filter
**Type**: Dropdown select

**Options**:
- All Segments
- Enterprise
- Mid-Enterprise
- Velocity
- Startup

**Default**: All Segments

**Behavior**: Filters all data to selected segment(s)

**Note**: On Summary page, this is overridden by individual panel selectors

---

### 3. Stage Filter
**Type**: Dropdown select

**Options**:
- All Stages
- Discovery
- Trial
- Negotiation
- Closed

**Default**: All Stages

**Behavior**: Filters to calls/accounts in selected stage

**Note**: Not applicable to Summary page (which shows all activity)

---

# Summary Page

## Purpose

**Answer the question**: "How is my sales team performing in terms of activity and coverage?"

**Primary Users**: Executives, Sales Leaders (COO, VP Sales, CRO, Dir Sales)

**Use Case**:
- Understand scale of sales motion (are we doing enough calls?)
- Assess capacity (are reps overloaded or underutilized?)
- Compare performance across segments
- Identify activity trends over time

---

## Layout

### Two-Panel Horizontal Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│                           SUMMARY                                    │
├──────────────────────────────┬──────────────────────────────────────┤
│        PANEL 1               │           PANEL 2                    │
│                              │                                      │
│  [Segment Selector ▼]        │  [Segment Selector ▼]               │
│                              │                                      │
│  ┌─── KPIs ────────────┐    │  ┌─── KPIs ────────────┐           │
│  │ Total Calls      125 │    │  │ Total Calls      328 │           │
│  │ Accounts         45  │    │  │ Accounts         102 │           │
│  │ Sales Reps       5   │    │  │ Sales Reps       12  │           │
│  │ Calls/Rep/Day    1.2 │    │  │ Calls/Rep/Day    1.5 │           │
│  │ Accounts/Rep     9.0 │    │  │ Accounts/Rep     8.5 │           │
│  └──────────────────────┘    │  └──────────────────────┘           │
│                              │                                      │
│  ┌─── Trend Charts ─────┐   │  ┌─── Trend Charts ─────┐          │
│  │ Calls/Rep/Day        │   │  │ Calls/Rep/Day        │          │
│  │ [Line Chart]         │   │  │ [Line Chart]         │          │
│  │                      │   │  │                      │          │
│  └──────────────────────┘   │  └──────────────────────┘          │
│                              │                                      │
│  ┌──────────────────────┐   │  ┌──────────────────────┐          │
│  │ Accounts/Rep         │   │  │ Accounts/Rep         │          │
│  │ [Line Chart]         │   │  │ [Line Chart]         │          │
│  │                      │   │  │                      │          │
│  └──────────────────────┘   │  └──────────────────────┘          │
│                              │                                      │
└──────────────────────────────┴──────────────────────────────────────┘
```

**Key Features**:
- Each panel is independent
- User can select different segments in each panel
- Allows side-by-side comparison (e.g., Enterprise vs Mid-Enterprise)
- All components in a panel update when segment changes

---

## Components

Each panel contains:
1. **Segment Selector** - Dropdown to choose segment
2. **KPI Cards** - 5 metrics showing activity and coverage
3. **Trend Charts** - 2 daily time series charts (calls, accounts)
4. **Distribution Charts** - 2 rep-level breakdowns (calls by rep, accounts by rep)

---

### 1. Segment Selector

**Type**: Dropdown select

**Options**:
- Enterprise
- Mid-Enterprise
- Velocity
- Startup
- (Any other segments defined in sales_reps table)

**Behavior**:
- Located at top of each panel
- Changing selection updates all KPIs and charts in that panel
- Independent selection per panel

**Default**:
- Panel 1: Enterprise
- Panel 2: Mid-Enterprise

---

### 2. KPI Cards

**Layout**: Vertical stack of 5 metrics

#### KPI 1: Total Calls
**Metric**: Total number of calls made by reps in this segment

**Calculation**:
```sql
SELECT COUNT(*) as total_calls
FROM calls c
JOIN accounts a ON c.account_id = a.id
WHERE a.primary_segment = [selected_segment]
```

**Display**:
- Number (e.g., "125")
- Label: "Total Calls"

---

#### KPI 2: Unique Accounts Engaged
**Metric**: Number of unique customer accounts engaged

**Calculation**:
```sql
SELECT COUNT(DISTINCT c.account_id) as unique_accounts
FROM calls c
JOIN accounts a ON c.account_id = a.id
WHERE a.primary_segment = [selected_segment]
```

**Display**:
- Number (e.g., "45")
- Label: "Unique Accounts"

---

#### KPI 3: Sales Reps
**Metric**: Number of active sales reps in this segment

**Calculation**:
```sql
SELECT COUNT(*) as rep_count
FROM sales_reps
WHERE segment = [selected_segment]
  AND is_active = 1
```

**Display**:
- Number (e.g., "5")
- Label: "Sales Reps"

---

#### KPI 4: Avg Calls/Rep/Day
**Metric**: Average number of calls per rep per working day

**Calculation**:
```python
# 1. Get all calls for segment
calls = get_calls_for_segment(segment)

# 2. Calculate total work days in date range
# Work days = Monday-Friday only
work_days = count_work_days(date_range)

# 3. Get rep count
rep_count = get_active_rep_count(segment)

# 4. Calculate
avg_calls_per_rep_per_day = len(calls) / (rep_count * work_days)
```

**Display**:
- Number with 1 decimal (e.g., "1.2")
- Label: "Calls/Rep/Day"

**Note**: Only count Monday-Friday as work days

---

#### KPI 5: Avg Accounts/Rep
**Metric**: Average number of unique accounts per rep

**Calculation**:
```python
# 1. Get unique accounts for segment
unique_accounts = get_unique_accounts_for_segment(segment)

# 2. Get rep count
rep_count = get_active_rep_count(segment)

# 3. Calculate
avg_accounts_per_rep = len(unique_accounts) / rep_count
```

**Display**:
- Number with 1 decimal (e.g., "9.0")
- Label: "Accounts/Rep"

---

### 3. Trend Chart: Total Calls Per Day

**Type**: Bar chart (time series)

**Purpose**: Show daily engagement volume to spot activity patterns and trends

**X-Axis**: Date (daily)

**Y-Axis**: Total number of calls

**Data Preparation**:

```python
def get_daily_calls(segment, date_from, date_to):
    """Get total calls per day for a segment."""

    query = """
        SELECT
            DATE(c.call_date) as call_day,
            COUNT(*) as total_calls
        FROM calls c
        JOIN accounts a ON c.account_id = a.id
        WHERE a.primary_segment = ?
          AND c.call_date >= ?
          AND c.call_date <= ?
        GROUP BY DATE(c.call_date)
        ORDER BY call_day
    """

    # Execute query
    results = execute_query(query, [segment, date_from, date_to])

    # Fill in missing dates with 0 (including weekends)
    date_range = generate_date_range(date_from, date_to)
    data_points = []

    results_dict = {row['call_day']: row['total_calls'] for row in results}

    for date in date_range:
        data_points.append({
            'date': date,
            'date_label': date.strftime('%b %d'),  # e.g., "Jan 15"
            'value': results_dict.get(date, 0)
        })

    return data_points
```

**Chart Properties**:
- Bar color: Blue (#3498db)
- Bar width: Auto (based on date range)
- Grid lines: Horizontal only
- Y-axis starts at 0
- Tooltip: "Jan 15, 2026: 23 calls"
- Hover: Highlight bar

**Behavior**:
- Shows all days in selected date range (including weekends with 0 calls)
- X-axis labels:
  - **7 days**: Show all dates (Mon, Tue, Wed, ...)
  - **30 days**: Show every 3-5 days to avoid crowding
  - **90 days**: Show every 7-10 days or month starts
- Responsive: Adjusts to panel width

---

### 4. Trend Chart: Unique Accounts Per Day

**Type**: Bar chart (time series)

**Purpose**: Show daily account coverage to understand engagement breadth

**X-Axis**: Date (daily)

**Y-Axis**: Number of unique accounts engaged

**Data Preparation**:

```python
def get_daily_unique_accounts(segment, date_from, date_to):
    """Get unique accounts engaged per day for a segment."""

    query = """
        SELECT
            DATE(c.call_date) as call_day,
            COUNT(DISTINCT c.account_id) as unique_accounts
        FROM calls c
        JOIN accounts a ON c.account_id = a.id
        WHERE a.primary_segment = ?
          AND c.call_date >= ?
          AND c.call_date <= ?
        GROUP BY DATE(c.call_date)
        ORDER BY call_day
    """

    # Execute query
    results = execute_query(query, [segment, date_from, date_to])

    # Fill in missing dates with 0 (including weekends)
    date_range = generate_date_range(date_from, date_to)
    data_points = []

    results_dict = {row['call_day']: row['unique_accounts'] for row in results}

    for date in date_range:
        data_points.append({
            'date': date,
            'date_label': date.strftime('%b %d'),
            'value': results_dict.get(date, 0)
        })

    return data_points
```

**Chart Properties**:
- Bar color: Green (#27ae60)
- Bar width: Auto (based on date range)
- Grid lines: Horizontal only
- Y-axis starts at 0
- Tooltip: "Jan 15, 2026: 12 accounts"
- Hover: Highlight bar

**Behavior**:
- Shows all days in selected date range (including weekends)
- X-axis labels: Same logic as Chart 3
- Responsive: Adjusts to panel width

**Insight**:
- User can mentally calculate accounts/rep by dividing by KPI #3 (Sales Reps)
- Helps identify: "We made 20 calls but only touched 5 accounts - lots of repeat touches"

---

### 5. Distribution Chart: Calls by Rep

**Type**: Bar chart (categorical)

**Purpose**: Show how call volume is distributed across sales reps in the segment

**X-Axis**: Sales rep email/name

**Y-Axis**: Total number of calls

**Data Preparation**:

```python
def get_calls_by_rep(segment, date_from, date_to):
    """Get total calls per rep for a segment."""

    query = """
        SELECT
            c.sales_rep_email as rep_email,
            COUNT(*) as total_calls
        FROM calls c
        JOIN accounts a ON c.account_id = a.id
        WHERE a.primary_segment = ?
          AND c.call_date >= ?
          AND c.call_date <= ?
        GROUP BY c.sales_rep_email
        ORDER BY total_calls DESC
    """

    # Execute query
    results = execute_query(query, [segment, date_from, date_to])

    data_points = []
    for row in results:
        # Extract name from email (before @)
        rep_name = row['rep_email'].split('@')[0]
        data_points.append({
            'rep_email': row['rep_email'],
            'rep_name': rep_name,
            'value': row['total_calls']
        })

    return data_points
```

**Chart Properties**:
- Bar color: Blue (#3498db)
- Bar width: Auto
- Grid lines: Horizontal only
- Y-axis starts at 0
- Tooltip: "rep_name: 45 calls"
- Hover: Highlight bar
- X-axis labels: Rep names (abbreviated if too long)

**Behavior**:
- Bars sorted by call count (descending) - highest volume reps on left
- If more than 10 reps, show top 10
- X-axis labels at 45° angle if crowded
- Responsive: Adjusts to panel width

**Insight**:
- Identify high and low performers by call volume
- Spot capacity imbalances (one rep doing 3x others)
- Helps answer: "Who's making the most calls?"

---

### 6. Distribution Chart: Unique Accounts by Rep

**Type**: Bar chart (categorical)

**Purpose**: Show how account coverage is distributed across sales reps in the segment

**X-Axis**: Sales rep email/name

**Y-Axis**: Number of unique accounts engaged

**Data Preparation**:

```python
def get_accounts_by_rep(segment, date_from, date_to):
    """Get unique accounts per rep for a segment."""

    query = """
        SELECT
            c.sales_rep_email as rep_email,
            COUNT(DISTINCT c.account_id) as unique_accounts
        FROM calls c
        JOIN accounts a ON c.account_id = a.id
        WHERE a.primary_segment = ?
          AND c.call_date >= ?
          AND c.call_date <= ?
        GROUP BY c.sales_rep_email
        ORDER BY unique_accounts DESC
    """

    # Execute query
    results = execute_query(query, [segment, date_from, date_to])

    data_points = []
    for row in results:
        # Extract name from email (before @)
        rep_name = row['rep_email'].split('@')[0]
        data_points.append({
            'rep_email': row['rep_email'],
            'rep_name': rep_name,
            'value': row['unique_accounts']
        })

    return data_points
```

**Chart Properties**:
- Bar color: Green (#27ae60)
- Bar width: Auto
- Grid lines: Horizontal only
- Y-axis starts at 0
- Tooltip: "rep_name: 12 accounts"
- Hover: Highlight bar
- X-axis labels: Rep names (abbreviated if too long)

**Behavior**:
- Bars sorted by account count (descending) - highest coverage reps on left
- If more than 10 reps, show top 10
- X-axis labels at 45° angle if crowded
- Responsive: Adjusts to panel width

**Insight**:
- Identify reps with broad vs narrow account focus
- Compare with Chart 5 to see: "Rep A has 50 calls but only 5 accounts (deep), Rep B has 30 calls across 15 accounts (broad)"
- Helps answer: "Who's covering the most accounts?"

---

## Data Requirements

### Tables Used
- `sales_reps` - rep count, segment
- `accounts` - account details, primary_segment
- `calls` - call records, call_date, account_id, sales_rep_email

### Key Fields
- `sales_reps.segment` - segment classification
- `sales_reps.is_active` - filter to active reps only
- `calls.call_date` - for time-based grouping
- `accounts.primary_segment` - filter calls by segment

### Date Handling
- **Daily granularity**: All charts show data by calendar day
- **Work Days**: Monday through Friday (for calls/rep/day KPI calculation)
- **Weekends included**: Charts show all 7 days (weekends typically 0 or low)
- **Missing dates**: If no calls on a date, show 0 (not gap in chart)

### Example Helper Functions

```python
from datetime import datetime, timedelta

def generate_date_range(start_date, end_date):
    """Generate list of all dates in range (inclusive)."""
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates

def count_work_days(start_date, end_date):
    """Count work days (Mon-Fri) in date range."""
    work_days = 0
    current = start_date
    while current <= end_date:
        # Monday=0, Friday=4
        if current.weekday() in [0, 1, 2, 3, 4]:
            work_days += 1
        current += timedelta(days=1)
    return work_days
```

---

## Visual Design

### Color Palette
- **Panel background**: White
- **KPI cards**: Light gray background (#f8f9fa)
- **KPI numbers**: Dark gray (#2c3e50)
- **KPI labels**: Medium gray (#7f8c8d)
- **Chart line (calls)**: Blue (#3498db)
- **Chart line (accounts)**: Green (#27ae60)
- **Grid lines**: Light gray (#ecf0f1)

### Typography
- **KPI numbers**: 32px, bold
- **KPI labels**: 14px, regular
- **Chart titles**: 16px, semibold
- **Axis labels**: 12px, regular

### Spacing
- Panel padding: 24px
- Between KPI cards: 16px
- Between KPIs and charts: 32px
- Between charts: 24px

---

## Implementation Notes

### Performance Considerations
1. **Caching**: Cache week-bucketed data to avoid recalculating on every segment change
2. **Query Optimization**: Use SQL window functions for date bucketing where possible
3. **Lazy Loading**: Load chart data only when panel is visible

### Edge Cases
1. **No data for segment**: Show "No data available" message
2. **Single rep**: Show metrics but note "Single rep - limited comparison value"
3. **Partial weeks**:
   - For KPIs: Include partial week data
   - For charts: Exclude current incomplete week from trend
4. **Rep count changes over time**: Use rep count at time of calculation (not historical)

### Mobile Responsiveness
- On mobile/tablet: Stack panels vertically instead of side-by-side
- Charts remain full-width
- KPI cards may display in 2-column grid on mobile

---

## Example Calculation Walkthrough

**Scenario**: Enterprise segment, Last 30 days (Dec 1 - Dec 30, 2025)

**Raw Data**:
- Active reps in Enterprise: 5
- Total calls in period: 87
- Unique accounts: 32
- Date range: Dec 1, 2025 - Dec 30, 2025 (30 days)
- Work days in period: 22 (excluding weekends)

**KPI Calculations**:

1. **Total Calls**: 87
2. **Unique Accounts**: 32
3. **Sales Reps**: 5
4. **Calls/Rep/Day**: 87 / (5 * 22) = 0.79 calls/rep/day
5. **Accounts/Rep**: 32 / 5 = 6.4 accounts/rep

**Chart Data Example** (Total Calls Per Day):

| Date    | Day of Week | Total Calls | Unique Accounts |
|---------|-------------|-------------|-----------------|
| Dec 1   | Sun         | 0           | 0               |
| Dec 2   | Mon         | 4           | 3               |
| Dec 3   | Tue         | 5           | 4               |
| Dec 4   | Wed         | 3           | 2               |
| Dec 5   | Thu         | 4           | 3               |
| Dec 6   | Fri         | 3           | 2               |
| Dec 7   | Sat         | 0           | 0               |
| Dec 8   | Sun         | 0           | 0               |
| Dec 9   | Mon         | 6           | 4               |
| ...     | ...         | ...         | ...             |

**User Insights**:
- Weekends consistently show 0 calls (expected)
- Weekdays average ~4 calls/day total
- With 5 reps, that's 0.8 calls/rep/day (matches KPI)
- User can spot: "Dec 9 had 6 calls - was that a big event?"

---

## Success Metrics

**Page is successful if users can answer:**
1. ✅ How many calls are my reps making per day?
2. ✅ Are we trending up or down in activity?
3. ✅ How does Enterprise compare to Mid-Enterprise in coverage?
4. ✅ Do we have capacity issues (reps overloaded)?
5. ✅ Are we engaging enough accounts per rep?

---

## Future Enhancements (Not in V1)

1. **Benchmark lines**: Add team average or target line to charts
2. **Seasonality indicators**: Highlight holiday weeks
3. **Export**: Download chart data as CSV
4. **Alerts**: Highlight weeks where metrics dropped >20%
5. **Rep details on hover**: Click KPI to see rep-level breakdown
6. **Compare to previous period**: Show % change from previous 90 days

---

## Questions to Resolve

1. **Segment naming**: Confirm exact segment names from `sales_reps.segment` column
   - Expected: enterprise, mid-enterprise, velocity, startup
   - Need exact casing (lowercase? title case?)

2. **Date range default**: Last 30 days (month view) seems reasonable - confirm?

3. **Rep count changes**: If a rep joins/leaves mid-period:
   - Use **current rep count** for all calculations (simpler - recommended)
   - Or track rep count historically (more accurate but complex)

4. **Holiday handling**: For calls/rep/day KPI:
   - Count all Mon-Fri as work days (simpler - recommended)
   - Or maintain holiday calendar and exclude company holidays

5. **Current/incomplete day**: For today (partial day):
   - Include in charts (shows current activity)
   - Or exclude until day is complete

---

*This spec will be expanded with additional pages (Accounts, Reps) as we define them.*
