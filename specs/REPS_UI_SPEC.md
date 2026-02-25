# Reps Dashboard UI Specification

## Overview
The Reps dashboard helps sales leaders understand rep performance, identify coaching opportunities, and track improvement over time.

## Key Goals
1. **Team Strengths/Weaknesses** - Identify where the team excels and struggles across stages
2. **Individual Rep Analysis** - Deep dive into each rep's strengths and weaknesses
3. **Performance Trends** - Track if reps are improving over time
4. **Account Engagement** - See which accounts each rep is working

---

## Page Layout

### Header
- Title: **"Sales Reps Performance"** with icon
- Date range filter (7/30/90 days)
- Segment filter (All, Enterprise, Scale, Velocity)
- Stage filter (All, Discovery, Trial, Negotiation)

### Summary Metrics (Top Row)
Four metric cards:
- **Active Reps** - Count of reps with calls in date range
- **Avg Team Score** - Average score across all frameworks (color-coded)
- **Total Calls** - Sum of all calls by all reps
- **Calls/Rep/Day** - Average daily call volume

---

## Section 1: Team Performance Heatmap

### Goal
Quick visual of team strengths/weaknesses across frameworks and reps

### Layout
**Heatmap Table:**
- **Rows:** Sales reps (sorted by segment, then name)
- **Columns:** Framework dimensions
  - Discovery: M, E, DD, DP, P, I, C, C (8 columns)
  - Trial: T, R, I, A, L (5 columns)
  - Negotiation: C, L, O, S, E (5 columns)
- **Cells:** Color-coded scores
  - Green (≥4.0)
  - Yellow (2.0-3.9)
  - Red (<2.0)
  - Gray (no data)
- **Cell values:** Display the score (e.g., "4.2")
- **Hover:** Show full dimension name and # of calls

### Additional Columns
- **Rep Name** (with segment tag)
- **# Calls** (in date range)
- **Overall Avg** (average across all dimensions with data)

### Sorting
- Allow sorting by any column
- Default: Sort by segment, then overall average (descending)

### Visual Enhancements
- Bold the highest score in each column (team strength)
- Underline the lowest score in each column (team weakness)
- Row highlight on hover

---

## Section 2: Framework Performance Charts

### Goal
Understand team performance by framework over time

### Layout
Three side-by-side line charts (or tabs):

#### Chart 1: MEDDPICC Trend (Discovery)
- **X-axis:** Date (weekly buckets)
- **Y-axis:** Average score (0-5)
- **Lines:** One line per MEDDPICC dimension (8 lines)
- **Legend:** Color-coded dimension labels
- **Tooltip:** Date, dimension, score, # of calls

#### Chart 2: TRIAL Trend
- Same structure as MEDDPICC but with 5 TRIAL dimensions

#### Chart 3: CLOSE Trend
- Same structure but with 5 CLOSE dimensions

### Insights Box (below charts)
- **Team Strengths:** Top 3 dimensions with highest avg scores
- **Team Weaknesses:** Bottom 3 dimensions with lowest avg scores
- **Improving:** Dimensions showing upward trend
- **Declining:** Dimensions showing downward trend

---

## Section 3: Individual Rep Deep Dive

### Trigger
Click on any rep name in the heatmap OR select from dropdown

### Layout (appears below heatmap when rep selected)

#### Rep Header
- **Rep name** with segment badge
- **Date range** of their activity
- **Summary stats:**
  - Total calls in period
  - Accounts worked
  - Avg score across all frameworks
  - Calls per week

#### Tab 1: Performance Overview

**Radar Chart (for each framework):**
- MEDDPICC radar: 8 dimensions
- TRIAL radar: 5 dimensions
- CLOSE radar: 5 dimensions
- Show rep's scores vs. team average as overlay
- Color: Rep = blue, Team = gray dotted line

**Strengths & Weaknesses Cards:**
- **Top 3 Strengths** (green cards)
  - Dimension name
  - Score
  - "X points above team avg"
- **Top 3 Weaknesses** (red cards)
  - Dimension name
  - Score
  - "X points below team avg"

#### Tab 2: Performance Trends

**Time Series Charts:**
- Line chart showing rep's scores over time for each framework
- X-axis: Date (weekly buckets)
- Y-axis: Score (0-5)
- Multiple lines for different dimensions
- Show trend line (linear regression)
- Highlight if improving/declining

**Improvement Metrics:**
- **Weeks active:** Count
- **Score delta:** Change from first week to last week
- **Trajectory:** Improving/Stable/Declining (with icon)

#### Tab 3: Accounts & Calls

**Accounts Table:**
- Columns:
  - Account domain
  - Current stage
  - # Calls by this rep
  - Last call date
  - Latest score (for current stage)
  - Health indicator (🟢🟡🔴)
- Sortable and filterable
- Click to expand call details

**Call History (expandable):**
- For each account, show list of calls:
  - Date
  - Stage
  - Scores
  - Link to Gong

---

## Section 4: Rep Comparison

### Goal
Compare 2-3 reps side by side

### Layout
- Dropdown to select 2-3 reps
- Show radar charts side by side
- Show key metrics comparison table
- Highlight differences (who's stronger where)

---

## Filters & Controls

### Sidebar Filters
1. **Date Range**
   - Last 7 days
   - Last 30 days
   - Last 90 days
   - Custom range

2. **Segment**
   - All
   - Enterprise
   - Scale
   - Velocity

3. **Stage Focus**
   - All stages
   - Discovery only
   - Trial only
   - Negotiation only

4. **Rep Filter**
   - Show all reps
   - Filter by segment
   - Search by name

### Additional Controls
- **Export to CSV** button (export heatmap data)
- **Refresh** button (reload data)

---

## Data Requirements

### From Database
- Sales reps table (email, name, segment, joining date)
- Calls table (filtered by date range)
- MEDDPICC scores (for discovery calls)
- TRIAL scores (for trial calls)
- CLOSE scores (for negotiation calls)
- Account information (domain, stage)

### Calculations Needed
1. **Rep aggregates:**
   - Average score per dimension per rep
   - Call count per rep
   - Calls per day per rep

2. **Team aggregates:**
   - Team average per dimension
   - Team total calls
   - Active reps count

3. **Time series:**
   - Weekly buckets of scores
   - Rolling averages (optional)
   - Trend lines

4. **Rep-account relationships:**
   - Which accounts each rep has called
   - Call frequency per account
   - Latest scores per account

---

## Color Scheme

### Score Colors
- **Green:** #2ecc71 (≥4.0) - Strong performance
- **Yellow:** #f39c12 (2.0-3.9) - Moderate performance
- **Red:** #e74c3c (<2.0) - Needs improvement
- **Gray:** #95a5a6 (no data)

### Rep Segments
- **Enterprise:** #3498db (blue)
- **Scale:** #9b59b6 (purple)
- **Velocity:** #e67e22 (orange)

### Comparison Colors
- **Rep 1:** #3498db (blue)
- **Rep 2:** #2ecc71 (green)
- **Rep 3:** #f39c12 (orange)
- **Team Avg:** #95a5a6 (gray, dotted line)

---

## Interactions

### Heatmap
- **Click cell:** Show dimension details modal
- **Click rep name:** Scroll to individual deep dive
- **Hover cell:** Show tooltip with dimension name, score, # calls
- **Sort column:** Click column header

### Charts
- **Hover line:** Show data point tooltip
- **Click legend:** Toggle dimension on/off
- **Click data point:** Show calls for that week

### Rep Deep Dive
- **Select rep:** Dropdown or click from heatmap
- **Tab switching:** Performance / Trends / Accounts
- **Expand account:** Show call list
- **Click call:** Link to Gong (external)

---

## Empty States

### No Data
- If no reps have calls in date range:
  - Show message: "No activity in selected date range"
  - Suggest: "Try expanding the date range"

### Partial Data
- If rep has calls but no scores for certain frameworks:
  - Show "N/A" or gray cells
  - Tooltip: "No [framework] calls in this period"

### New Rep
- If rep joined recently:
  - Badge: "New" (joined <30 days ago)
  - Note: "Limited historical data"

---

## Mobile Considerations
- Heatmap: Horizontal scroll on mobile
- Charts: Stack vertically instead of side-by-side
- Tables: Responsive with essential columns only
- Rep deep dive: Full-screen modal on mobile

---

## Performance Considerations
- Lazy load individual rep details (only when clicked)
- Cache team aggregates (update every 5 minutes)
- Paginate accounts table if >50 rows
- Limit time series to weekly buckets for 90-day range

---

## Future Enhancements
1. **Coaching Mode:** Mark reps for coaching, track coaching sessions
2. **Goals:** Set target scores per rep, track progress
3. **Certifications:** Track MEDDPICC certification status
4. **Leaderboard:** Gamification with rankings
5. **Peer Comparison:** Compare rep to similar reps (same segment/tenure)
6. **Call Quality:** Listen to calls directly in UI (Gong iframe)
7. **AI Insights:** Suggest coaching areas based on trends

---

## Technical Notes

### Data Flow
1. Load sales reps from database
2. Fetch calls for date range, filtered by segment/stage
3. Load scores for each call (MEDDPICC/TRIAL/CLOSE)
4. Aggregate scores by rep and dimension
5. Calculate team averages
6. Generate time series data (weekly buckets)

### Query Optimization
- Use single query with JOINs to fetch rep + calls + scores
- Pre-calculate aggregates where possible
- Index on (sales_rep_email, call_date, primary_stage)

### Caching Strategy
- Cache team aggregates for 5 minutes
- Cache individual rep data until page refresh
- Invalidate on date range change

---

## Questions to Consider
1. Should we show terminated/inactive reps?
2. How to handle reps who change segments?
3. Should "team average" include all reps or just active ones?
4. What's the minimum # of calls to show a score? (avoid small sample sizes)
5. Should we weight recent calls more heavily?
6. Do we want to compare reps within same segment only?
