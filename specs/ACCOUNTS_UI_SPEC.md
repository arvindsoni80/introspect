# Accounts Page UI Specification

## Overview

The Accounts page helps sales leaders and reps understand deal health, identify at-risk opportunities, and track account progression across stages.

**Primary Questions:**
- Which accounts need attention right now?
- Where are deals stalling?
- How healthy are accounts in each stage?
- Which accounts are progressing well vs struggling?

**Primary Users:**
- Sales Leaders (VP Sales, Dir Sales, Sales Managers)
- Individual Sales Reps
- Revenue Operations

---

## Page Layout

### Structure

```
┌────────────────────────────────────────────────────────────────┐
│                         ACCOUNTS                                │
├────────────────────────────────────────────────────────────────┤
│  Sidebar Filters:                                              │
│  - Date Range (7/30/90 days)                                   │
│  - Segment (All/Enterprise/Mid-Enterprise/...)                 │
│  - Stage (All/Discovery/Trial/Negotiation/Closed)              │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  VIEW 1: STAGE HEALTH VISUALIZATION                            │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐                     │
│  │  🔍 Discovery   │  │  🧪 Trial       │                     │
│  │  [Bubble Chart] │  │  [Bubble Chart] │                     │
│  └─────────────────┘  └─────────────────┘                     │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐                     │
│  │  💼 Negotiation │  │  ✅ Closed      │                     │
│  │  [Bubble Chart] │  │  [Bubble Chart] │                     │
│  └─────────────────┘  └─────────────────┘                     │
│                                                                 │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  VIEW 2: ACCOUNTS TABLE                                        │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ Account  │ Stage │ Calls │ Days │ Score │ Health │ Rep  │ │
│  ├──────────────────────────────────────────────────────────┤ │
│  │ acme.com │ Trial │  12   │  45  │  3.2  │  🟡    │ John │ │
│  │ [ Click to expand for details ]                          │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## View 1: Stage Health Visualization

### Purpose

**Answer these questions at a glance:**
- Which accounts are fresh and active vs stale and dying?
- Are we engaging frequently enough in each stage?
- Which deals need immediate attention?

### Layout: 4-Panel Grid (2x2)

One bubble scatter plot per stage:
- Discovery (top left)
- Trial (top right)
- Negotiation (bottom left)
- Closed (bottom right)

---

### Bubble Scatter Plot Specification

**Chart Type**: Scatter plot with sized bubbles

**Axes:**
- **X-Axis**: Days in Current Stage
  - Range: 0 to max (auto-scale)
  - Label: "Days in Stage"
  - Grid lines: Every 7 days (weekly markers)

- **Y-Axis**: Number of Calls in Current Stage
  - Range: 0 to max (auto-scale)
  - Label: "Calls"
  - Grid lines: Every 5 calls

**Bubbles:**
- **Size**: Proportional to total calls across ALL stages (engagement history)
  - Min size: 10px
  - Max size: 40px
  - Scale: `bubble_size = 10 + (total_calls / max_total_calls) * 30`

- **Color**: Based on health score (stage-specific framework)
  - **Discovery**: MEDDPICC overall_score
  - **Trial**: TRIAL overall_score
  - **Negotiation**: CLOSE overall_score
  - **Closed**: Win/Loss outcome or final score

  **Color Scale:**
  - 🟢 **Dark Green** (score >= 4.0): `#2ecc71` - Healthy
  - 🟡 **Yellow** (score 2.5-3.9): `#f39c12` - At Risk
  - 🔴 **Red** (score < 2.5): `#e74c3c` - Critical
  - ⚪ **Gray** (no score): `#95a5a6` - Not Evaluated

**Hover Tooltip:**
```
acme.com
Stage: Trial | Days: 45 | Calls: 12
Trial Score: 3.2/5.0 🟡
Total Calls (all stages): 28
Rep: john.doe@company.com
Click to view details
```

**Interactivity:**
- Click bubble → Scroll to and expand that account in the table below
- Hover → Show tooltip with account details

---

### Data Preparation

```python
def get_stage_health_data(segment: str, stage: str, date_from: datetime, date_to: datetime):
    """Get bubble chart data for a specific stage."""

    query = """
        SELECT
            a.id,
            a.domain,
            a.current_stage,
            a.primary_sales_rep,
            a.total_calls,
            -- Days in current stage
            JULIANDAY('now') - JULIANDAY(
                COALESCE(
                    (SELECT MAX(call_date) FROM calls c2
                     WHERE c2.account_id = a.id
                     AND c2.primary_stage != a.current_stage),
                    a.first_call_date
                )
            ) as days_in_stage,
            -- Calls in current stage
            (SELECT COUNT(*) FROM calls c3
             WHERE c3.account_id = a.id
             AND c3.primary_stage = a.current_stage) as calls_in_stage
        FROM accounts a
        WHERE a.current_stage = ?
          AND a.primary_segment = ?
    """

    # Execute query
    results = execute_query(query, [stage, segment])

    # For each account, get the latest score
    data_points = []
    for row in results:
        account_id = row['id']

        # Get latest score for this stage
        if stage == 'discovery':
            scores = get_latest_meddpicc_score(account_id)
            health_score = scores.overall_score if scores else None
        elif stage == 'trial':
            scores = get_latest_trial_score(account_id)
            health_score = scores.overall_score if scores else None
        elif stage == 'negotiation':
            scores = get_latest_close_score(account_id)
            health_score = scores.overall_score if scores else None
        else:  # closed
            # For closed, could use final score or outcome
            health_score = None

        data_points.append({
            'account_id': row['id'],
            'domain': row['domain'],
            'days_in_stage': row['days_in_stage'],
            'calls_in_stage': row['calls_in_stage'],
            'total_calls': row['total_calls'],
            'health_score': health_score,
            'rep': row['primary_sales_rep'],
            'stage': row['current_stage']
        })

    return data_points
```

---

### Chart Behavior & Insights

#### Quadrant Interpretation

```
High Calls │                    │
     ↑     │  🟢 Active &       │  🟡 Heavy Touch   │
           │     Healthy        │     Needs Review  │
           │                    │                   │
           ├────────────────────┼───────────────────┤
           │  🔴 Struggling     │  🔴 Stale &       │
           │     Needs Help     │     Dying         │
Low Calls  │                    │                   │
           └────────────────────┴───────────────────┘
           Few Days              Many Days
                    Days in Stage →
```

**Key Patterns:**

1. **Top Left (Few days, Many calls, Green)**
   - **Interpretation**: Fresh, actively engaged, healthy
   - **Action**: Keep momentum, monitor progress

2. **Top Right (Many days, Many calls, Yellow/Red)**
   - **Interpretation**: Heavy touch but not advancing - something's stuck
   - **Action**: Review strategy, identify blockers

3. **Bottom Left (Few days, Few calls, Any color)**
   - **Interpretation**: Just entered stage, normal
   - **Action**: Engage more to move forward

4. **Bottom Right (Many days, Few calls, Red)**
   - **Interpretation**: Stale, dying, at-risk
   - **Action**: URGENT - Re-engage or mark as lost

#### Alert Thresholds (Customizable)

Define warning zones with vertical/horizontal reference lines:

**Discovery:**
- Days threshold: 30 days (vertical line)
- Calls threshold: 3 calls (horizontal line)
- Alert: `days > 30 AND calls < 3` → Critical

**Trial:**
- Days threshold: 21 days (3 weeks)
- Calls threshold: 5 calls
- Alert: `days > 21 AND calls < 5` → At Risk

**Negotiation:**
- Days threshold: 14 days (2 weeks)
- Calls threshold: 3 calls
- Alert: `days > 14 AND calls < 3` → Critical

---

### Chart Properties

**Title**: Stage emoji + name (e.g., "🔍 Discovery" or "🧪 Trial")

**Size**:
- Height: 350px
- Width: Half panel width (2 charts per row)

**Style:**
- Background: White
- Border: 1px solid #e2e8f0
- Shadow: `0 1px 3px 0 rgba(0, 0, 0, 0.1)`
- Border radius: 8px

**Grid Lines:**
- X-axis: Every 7 days (weekly)
- Y-axis: Every 5 calls
- Color: #f1f5f9 (light gray)

**Reference Lines (optional):**
- Vertical line at alert threshold (e.g., 30 days) - dashed, red
- Horizontal line at alert threshold (e.g., 3 calls) - dashed, red

**Account Count Badge:**
- Show total accounts in this stage
- Display in top-right corner of each chart
- Example: "12 accounts"

---

## View 2: Accounts Table

### Purpose

Detailed list view with sorting, filtering, and expandable account details.

### Table Layout

**Columns:**
1. **Account** (domain)
   - Example: `acme.com`
   - Sortable: Yes
   - Width: 20%

2. **Stage**
   - Icon + name (e.g., "🔍 Discovery")
   - Sortable: Yes
   - Width: 15%

3. **Calls**
   - Total calls for this account (all stages)
   - Sortable: Yes (default sort: descending)
   - Width: 10%

4. **Days in Stage**
   - Days since entered current stage
   - Sortable: Yes
   - Width: 12%

5. **Last Call**
   - Date of most recent call
   - Format: "Jan 15, 2026" or "2d ago"
   - Sortable: Yes
   - Width: 12%

6. **Score**
   - Stage-appropriate score (MEDDPICC/TRIAL/CLOSE)
   - Format: "3.2/5.0"
   - Sortable: Yes
   - Width: 10%

7. **Health**
   - Emoji indicator: 🟢 🟡 🔴 ⚪
   - Based on score thresholds
   - Sortable: Yes
   - Width: 8%

8. **Rep**
   - Primary sales rep (name extracted from email)
   - Example: "john.doe"
   - Sortable: Yes
   - Width: 13%

**Default Sort:** Days in Stage (descending) - oldest first

**Row Styling:**
- Hover: Light gray background (#f8f9fa)
- Border: 1px solid #e2e8f0 between rows
- Padding: 12px
- Cursor: pointer

**Empty State:**
- Message: "No accounts match your filters"
- Show illustration or icon
- Suggest: "Try adjusting filters"

---

### Table Interactivity

**Click Row → Expand Details:**

When user clicks a row, expand it to show:

```
┌──────────────────────────────────────────────────────────────┐
│ acme.com | 🧪 Trial | 12 calls | 45 days | 3.2/5.0 | 🟡      │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ACCOUNT DETAILS                                             │
│                                                               │
│  ┌─ Account Info ──────────────────────────────────┐        │
│  │ Domain: acme.com                                 │        │
│  │ Primary Rep: john.doe@company.com                │        │
│  │ Segment: Enterprise                              │        │
│  │ First Call: Dec 1, 2025                          │        │
│  │ Last Call: Jan 15, 2026                          │        │
│  │ Total Calls: 28 (Discovery: 8, Trial: 12, ...)  │        │
│  └──────────────────────────────────────────────────┘        │
│                                                               │
│  ┌─ Customer Contacts ─────────────────────────────┐        │
│  │ • John Smith (CEO) - john@acme.com               │        │
│  │ • Jane Doe (VP Eng) - jane@acme.com              │        │
│  └──────────────────────────────────────────────────┘        │
│                                                               │
│  ┌─ Stage Scores & Health ─────────────────────────┐        │
│  │                                                   │        │
│  │  [MEDDPICC Chart]  [TRIAL Chart]  [CLOSE Chart] │        │
│  │                                                   │        │
│  └──────────────────────────────────────────────────┘        │
│                                                               │
│  ┌─ Call History by Stage ─────────────────────────┐        │
│  │                                                   │        │
│  │  Discovery (8 calls)                             │        │
│  │  ────────────────────────────────────────────    │        │
│  │  Dec 1  | MEDDPICC: 2.8 | [View Call →]         │        │
│  │  Dec 5  | MEDDPICC: 3.1 | [View Call →]         │        │
│  │  ...                                              │        │
│  │                                                   │        │
│  │  Trial (12 calls)                                │        │
│  │  ────────────────────────────────────────────    │        │
│  │  Dec 15 | TRIAL: 3.2 | [View Call →]            │        │
│  │  Dec 18 | TRIAL: 3.5 | [View Call →]            │        │
│  │  ...                                              │        │
│  │                                                   │        │
│  └──────────────────────────────────────────────────┘        │
│                                                               │
│  [Close Details ✕]                                           │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

### Enhanced Detail View Components

#### 1. Account Info Card
**Component**: shadcn Card with grid layout

```html
<Card>
  <CardHeader>Account Information</CardHeader>
  <CardContent>
    <Grid cols={2}>
      <Label>Domain</Label> <Value>acme.com</Value>
      <Label>Primary Rep</Label> <Value>john.doe@company.com</Value>
      <Label>Segment</Label> <Value>Enterprise</Value>
      <Label>Deal Status</Label> <Value>Active</Value>
      <Label>First Call</Label> <Value>Dec 1, 2025</Value>
      <Label>Last Call</Label> <Value>Jan 15, 2026 (2 days ago)</Value>
      <Label>Total Calls</Label> <Value>28</Value>
      <Label>Stage Distribution</Label>
      <Value>Discovery: 8 | Trial: 12 | Negotiation: 8</Value>
    </Grid>
  </CardContent>
</Card>
```

**Styling:**
- White background
- Border: #e2e8f0
- Shadow: subtle
- Grid: 2 columns, labels in gray, values in dark text

---

#### 2. Customer Contacts Card
**Component**: shadcn Card with list

```html
<Card>
  <CardHeader>Customer Contacts</CardHeader>
  <CardContent>
    <List>
      <ListItem>
        <Avatar>JS</Avatar>
        <div>
          <Name>John Smith</Name>
          <Role>CEO</Role>
          <Email>john@acme.com</Email>
        </div>
      </ListItem>
      ...
    </List>
  </CardContent>
</Card>
```

**Data Source:**
```sql
SELECT DISTINCT
    cp.participant_name,
    cp.participant_role,
    cp.participant_email
FROM call_participants cp
JOIN calls c ON cp.call_id = c.call_id
WHERE c.account_id = ?
  AND cp.is_customer = 1
ORDER BY cp.participant_name
```

---

#### 3. Stage Scores & Health Charts

**Layout**: 3 charts side-by-side (if account has calls in those stages)

- **MEDDPICC Chart** (Discovery calls)
  - Bar chart with 8 dimensions (M, E, DD, DP, P, I, C, C)
  - Shows most recent Discovery call scores
  - Color-coded by score (red/yellow/green)

- **TRIAL Chart** (Trial calls)
  - Bar chart with 5 dimensions (T, R, I, A, L)
  - Shows most recent Trial call scores
  - Color-coded by score

- **CLOSE Chart** (Negotiation calls)
  - Bar chart with 5 dimensions (C, L, O, S, E)
  - Shows most recent Negotiation call scores
  - Color-coded by score

**Enhancement**: Use shadcn Card wrapper for each chart

```html
<div class="grid grid-cols-3 gap-4">
  <Card>
    <CardHeader>Discovery Health</CardHeader>
    <CardContent>
      [MEDDPICC Plotly Chart]
      <p>Latest: Dec 5, Score: 3.1/5.0</p>
    </CardContent>
  </Card>

  <Card>
    <CardHeader>Trial Health</CardHeader>
    <CardContent>
      [TRIAL Plotly Chart]
      <p>Latest: Jan 15, Score: 3.5/5.0</p>
    </CardContent>
  </Card>

  <Card>
    <CardHeader>Negotiation Health</CardHeader>
    <CardContent>
      [CLOSE Plotly Chart]
      <p>Latest: N/A</p>
    </CardContent>
  </Card>
</div>
```

---

#### 4. Call History by Stage

**Component**: Accordion/Collapsible sections per stage

```html
<Card>
  <CardHeader>Call History</CardHeader>
  <CardContent>

    <Accordion>
      <AccordionItem value="discovery">
        <AccordionTrigger>🔍 Discovery (8 calls)</AccordionTrigger>
        <AccordionContent>
          <Table>
            <Row>
              <Date>Dec 1, 2025</Date>
              <Score>MEDDPICC: 2.8/5.0 🟡</Score>
              <Link>[View Call →]</Link>
            </Row>
            <Row>
              <Date>Dec 5, 2025</Date>
              <Score>MEDDPICC: 3.1/5.0 🟡</Score>
              <Link>[View Call →]</Link>
            </Row>
            ...
          </Table>
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="trial">
        <AccordionTrigger>🧪 Trial (12 calls)</AccordionTrigger>
        <AccordionContent>
          [Similar table for Trial calls]
        </AccordionContent>
      </AccordionItem>

      ...
    </Accordion>

  </CardContent>
</Card>
```

**Call Row Data:**
- Date
- Stage-appropriate score with emoji
- Duration (if available)
- Participants count
- Link to Gong recording
- Link to detailed call view (if implementing call detail page)

---

## Sidebar Filters

**Location**: Left sidebar (consistent with Summary page)

**Components:**

### 1. Date Range
**Type**: Radio buttons

**Options:**
- Last 7 days
- Last 30 days
- Last 90 days

**Default**: Last 30 days

**Behavior**: Filters accounts by `last_call_date`

---

### 2. Segment Filter
**Type**: Dropdown select

**Options:**
- All Segments
- Enterprise
- Mid-Enterprise
- Velocity
- Startup
- (Any other segments from sales_reps table)

**Default**: All Segments

**Behavior**: Filters accounts by `primary_segment`

---

### 3. Stage Filter
**Type**: Dropdown select

**Options:**
- All Stages
- Discovery
- Trial
- Negotiation
- Closed

**Default**: All Stages

**Behavior**:
- Filters accounts by `current_stage`
- When "All Stages" selected, show all 4 bubble charts
- When specific stage selected, show only that bubble chart (larger)

---

### 4. Health Filter (NEW)
**Type**: Checkbox group

**Options:**
- 🟢 Healthy (score >= 4.0)
- 🟡 At Risk (score 2.5-3.9)
- 🔴 Critical (score < 2.5)
- ⚪ Not Evaluated (no score)

**Default**: All selected

**Behavior**: Filters both bubble charts and table by health status

---

### 5. Rep Filter (NEW)
**Type**: Multi-select dropdown

**Options:**
- All Reps
- john.doe@company.com
- jane.smith@company.com
- ...

**Default**: All Reps

**Behavior**: Filters accounts by `primary_sales_rep`

---

## Data Requirements

### Tables Used
- `accounts` - account info, current stage, segment
- `calls` - call records with stage
- `stage_transitions` - stage history to calculate days_in_stage
- `call_meddpicc_scores` - Discovery scores
- `call_trial_scores` - Trial scores
- `call_close_scores` - Negotiation scores
- `call_participants` - customer contacts
- `sales_reps` - rep information

### Key Calculations

**Days in Stage:**
```sql
-- Time since last stage transition
JULIANDAY('now') - JULIANDAY(
    COALESCE(
        (SELECT MAX(call_date) FROM calls
         WHERE account_id = ? AND primary_stage != current_stage),
        first_call_date
    )
)
```

**Calls in Current Stage:**
```sql
SELECT COUNT(*)
FROM calls
WHERE account_id = ? AND primary_stage = current_stage
```

**Latest Score:**
```sql
-- For Discovery
SELECT * FROM call_meddpicc_scores cms
JOIN calls c ON cms.call_id = c.call_id
WHERE c.account_id = ?
ORDER BY c.call_date DESC
LIMIT 1
```

---

## Visual Design

### Color Palette

**Stage Colors:**
- Discovery: `#3498db` (Blue)
- Trial: `#f39c12` (Orange)
- Negotiation: `#9b59b6` (Purple)
- Closed: `#2ecc71` (Green)

**Health Colors:**
- Healthy: `#2ecc71` (Green)
- At Risk: `#f39c12` (Yellow)
- Critical: `#e74c3c` (Red)
- Not Evaluated: `#95a5a6` (Gray)

**UI Elements:**
- Card background: `#ffffff` (White)
- Border: `#e2e8f0` (Light gray)
- Hover: `#f8f9fa` (Very light gray)
- Shadow: `0 1px 3px 0 rgba(0, 0, 0, 0.1)`

### Typography
- Headers: 18px, semibold
- Subheaders: 16px, medium
- Body: 14px, regular
- Labels: 12px, medium, gray
- Values: 14px, regular, dark

---

## User Workflows

### Workflow 1: Identify At-Risk Deals
1. Load Accounts page
2. Look at bubble charts - find red bubbles in bottom-right quadrants
3. Click on red bubble → scroll to account in table
4. Expand account details
5. Review score breakdown and call history
6. Identify gaps (e.g., "Economic Buyer not identified")
7. Take action (schedule call, update strategy)

### Workflow 2: Stage Health Check
1. Filter by stage (e.g., "Trial")
2. View single large bubble chart for Trial
3. Identify clusters:
   - Top-left: Healthy, progressing
   - Bottom-right: Stale, need re-engagement
4. Sort table by "Days in Stage" (descending)
5. Review oldest trials first

### Workflow 3: Rep Performance Review
1. Filter by rep (e.g., "john.doe")
2. View all their accounts across stages
3. Assess:
   - Are accounts progressing? (bubbles moving left-to-right over time)
   - Are scores improving? (color changes)
   - Any stale accounts? (bottom-right bubbles)
4. Provide coaching on specific accounts

### Workflow 4: Deep Dive on Account
1. Find account in table (search or scroll)
2. Click to expand
3. Review:
   - Customer contacts (who are we talking to?)
   - Score trends (improving or declining?)
   - Call frequency (engaged or stale?)
4. Click "View Call" to listen to specific calls in Gong
5. Update strategy based on insights

---

## Implementation Notes

### Performance Considerations
1. **Bubble chart data**: Cache for 5 minutes
2. **Table pagination**: Load 50 accounts at a time
3. **Detail expansion**: Lazy-load call history on expand
4. **Score calculations**: Pre-compute and store in cache

### Edge Cases
1. **No score for account**: Show gray bubble, "Not Evaluated" in table
2. **Account just entered stage**: 0-1 days in stage is normal
3. **Closed accounts**: May not have recent scores, show last known
4. **Multiple reps**: Use `primary_sales_rep`, note in details if multiple

### Mobile Responsiveness
- Bubble charts: Stack vertically (1 per row) on mobile
- Table: Horizontal scroll or card layout
- Detail view: Full-width cards, stack vertically

---

## Success Metrics

**Page is successful if users can answer:**
1. ✅ Which accounts need immediate attention?
2. ✅ Are deals progressing or stalling in each stage?
3. ✅ How healthy are my Trial accounts overall?
4. ✅ Which accounts are at risk of going dark?
5. ✅ What's the distribution of engagement across my pipeline?
6. ✅ Where are the qualification gaps in Discovery accounts?

---

## Future Enhancements (Not in V1)

1. **Trend arrows**: Show if days_in_stage is increasing/decreasing
2. **Bulk actions**: Select multiple accounts, assign to rep, update stage
3. **Saved views**: Save filter combinations (e.g., "My At-Risk Trials")
4. **Account comparison**: Compare 2-3 accounts side-by-side
5. **Export**: Download filtered accounts as CSV
6. **AI insights**: "This account is at risk because..." auto-generated
7. **Stage timeline**: Visual timeline showing stage progression
8. **Email alerts**: Notify when account crosses threshold (e.g., 30 days in Discovery)

---

*This spec combines the new bubble scatter visualization with the existing table/detail views, enhanced with shadcn-ui components for a polished, professional interface.*
