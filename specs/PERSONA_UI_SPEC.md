# Persona Analysis UI Specification

## Overview

The Persona page provides insights into customer questions organized by persona type (Decision Makers, Influencers, Users). This enables sales and product teams to understand what different stakeholders care about, prepare better for calls, and tailor messaging by role.

## Goals

1. **Understand Persona Engagement**: Show who we're talking to across deals (CTO, VP Eng, Directors, Engineers)
2. **Identify Recurring Questions**: Surface the most common questions asked by each persona type
3. **Enable Deep Dives**: Link to specific calls where questions were asked for context
4. **Inform Sales Enablement**: Help reps prepare for specific persona types
5. **Guide Product Positioning**: Understand what matters most to different stakeholders

---

## Persona Definitions

### Decision Makers (DM)
**Who they are**: C-level executives and VPs who make final purchase decisions

**Title Patterns** (case-insensitive matching):
- `CTO`, `Chief Technology Officer`
- `VP`, `Vice President`
- `SVP`, `Senior Vice President`
- `EVP`, `Executive Vice President`
- `Chief`, `Head of Engineering`, `Head of Technology`

**What they care about**: ROI, strategic fit, risk, vendor stability, executive-level value prop

---

### Influencers (CH)
**Who they are**: Directors and senior managers who advocate for the product internally

**Title Patterns** (case-insensitive matching):
- `Director`
- `Senior Manager`, `Sr Manager`, `Sr. Manager`
- `Head of` (when not VP/C-level)
- `Lead` (Platform Lead, Engineering Lead, etc.)
- `Principal` (Principal Engineer, Principal Architect)
- `Staff Engineer`, `Staff Software Engineer`

**What they care about**: Team impact, technical feasibility, implementation effort, internal advocacy

---

### Users (US)
**Who they are**: Individual contributors who will use the product day-to-day

**Title Patterns** (case-insensitive matching):
- `Software Engineer`, `Engineer`
- `Developer`, `Dev`
- `SDE`, `Software Development Engineer`
- `Programmer`
- `Analyst` (Technical Analyst, Data Analyst)
- No title or generic titles

**What they care about**: Usability, workflow integration, learning curve, day-to-day productivity

---

## Page Layout

### Header
```
🎭 Persona Analysis

[Date Range Filter: Last 30 days ▼] [Segment Filter: All ▼] [Stage Filter: All ▼]
```

### Section 1: Persona Engagement Summary

**Top metrics row** (3 cards):
```
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│ 👔 Decision Makers      │  │ 🤝 Influencers            │  │ 👨‍💻 Users               │
│                         │  │                         │  │                         │
│ 47 participants         │  │ 123 participants        │  │ 89 participants         │
│ 234 questions asked     │  │ 567 questions asked     │  │ 312 questions asked     │
│ 32 accounts             │  │ 45 accounts             │  │ 38 accounts             │
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘
```

**Engagement breakdown** (bar chart or table):
```
Most Common Titles by Persona:

Decision Makers:
  VP Engineering         : ████████████████ 15
  CTO                   : ████████████ 12
  SVP Technology        : ████████ 8
  ...

Influencers:
  Director of Engineering: ████████████████████ 20
  Senior Manager DevOps  : ██████████████ 14
  Engineering Lead       : ████████████ 12
  ...

Users:
  Software Engineer      : ████████████████████████ 24
  Senior Software Engineer: ████████████████████ 20
  Developer              : ████████████ 12
  ...
```

---

### Section 2: Top Questions by Persona

**Layout**: 3 tabs or 3 expandable sections, one per persona

#### Tab 1: Decision Makers

```
🔍 Top Recurring Questions from Decision Makers

┌─────────────────────────────────────────────────────────────────────────┐
│ #  │ Question                                                  │ Count │
├────┼───────────────────────────────────────────────────────────┼───────┤
│ 1  │ What's your pricing model for enterprise deployments?     │  12   │
│    │ 📞 Asked in: 3 calls (show/hide)                          │       │
│    │    • [Capital One] Discovery Call - Feb 10                │       │
│    │    • [Visa] Technical Deep Dive - Feb 8                   │       │
│    │    • [HP] Commercial Discussion - Feb 5                   │       │
├────┼───────────────────────────────────────────────────────────┼───────┤
│ 2  │ How do you ensure data security and compliance?           │  10   │
│    │ 📞 Asked in: 4 calls (show/hide)                          │       │
│    │    • [Cisco] Security Review - Feb 12                     │       │
│    │    • [KPMG] Compliance Discussion - Feb 9                 │       │
│    │    • [Teradata] Architecture Review - Feb 7               │       │
│    │    • [Salesforce] Initial Call - Feb 3                    │       │
├────┼───────────────────────────────────────────────────────────┼───────┤
│ 3  │ What's the implementation timeline?                       │  8    │
│    │ 📞 Asked in: 3 calls (show/hide)                          │       │
├────┼───────────────────────────────────────────────────────────┼───────┤
│ ... (show top 10-15 questions)                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Features**:
- Questions sorted by frequency (descending)
- Expandable call list for each question (collapsed by default)
- Click on call link → opens modal or sidebar with:
  - Full call details
  - Link to Gong (external)
  - Full question in context (if available)
  - Who asked it (name, title, company)

#### Tab 2: Influencers
Similar layout as Decision Makers tab

#### Tab 3: Users
Similar layout as Decision Makers tab

---

## Data Requirements

### Queries Needed

**1. Get all participants with questions in time range:**
```sql
SELECT
  cp.name,
  cp.title,
  cp.speaker_questions,
  cp.question_count,
  c.call_id,
  c.call_title,
  c.call_date,
  c.primary_stage,
  a.domain,
  a.primary_segment
FROM call_participants cp
JOIN calls c ON cp.call_id = c.call_id
JOIN accounts a ON c.account_id = a.id
WHERE cp.affiliation = 'External'
  AND cp.speaker_questions IS NOT NULL
  AND cp.question_count > 0
  AND c.call_date >= ?
  [AND a.primary_segment = ?]
  [AND c.primary_stage = ?]
```

**2. Persona Classification Logic:**
```python
def classify_persona(title: str) -> str:
    """
    Classify participant into persona based on title.
    Returns: 'Decision Maker', 'Influencer', 'User', or 'Unknown'
    """
    if not title:
        return 'User'  # Default to User

    title_lower = title.lower()

    # Decision Makers (check first - most specific)
    dm_patterns = ['cto', 'chief technology', 'chief information',
                   'vp', 'vice president', 'svp', 'evp',
                   'head of engineering', 'head of technology', 'head of product']
    if any(pattern in title_lower for pattern in dm_patterns):
        return 'Decision Maker'

    # Influencers (check second)
    ch_patterns = ['director', 'senior manager', 'sr manager', 'sr. manager',
                   'head of', 'lead', 'principal', 'staff engineer',
                   'distinguished engineer', 'architect']
    if any(pattern in title_lower for pattern in ch_patterns):
        return 'Influencer'

    # Users (default)
    return 'User'
```

**3. Question Similarity/Clustering:**

For v1: Use exact string matching (case-insensitive, strip whitespace)

For v2+: Consider semantic similarity using embeddings to group similar questions:
- "What's your pricing?"
- "How much does it cost?"
- "Can you share pricing details?"

→ Should be grouped as one recurring question

---

## Filters

### Date Range Filter
- Last 7 days
- Last 30 days (default)
- Last 90 days
- All time
- Custom range

### Segment Filter
- All (default)
- Enterprise
- Mid-Enterprise
- Scale
- Velocity

### Stage Filter
- All (default)
- Discovery
- Trial
- Negotiation
- Closed

**Behavior**: Filters apply to both summary metrics and questions list

---

## Interactions

### Click on Question Row
**Behavior**: Expand/collapse call list for that question

### Click on Call Link
**Behavior**: Open call details modal/sidebar showing:
- Call title
- Date
- Account name
- Stage
- Participants on the call
- Link to Gong recording (external link icon)
- Full context: Show 2-3 lines before and after the question in transcript

### Export Functionality (Future)
**Button**: "Export Questions CSV"
**Behavior**: Download CSV with columns:
- Persona
- Question
- Frequency
- Accounts Asked (comma-separated)
- Most Recent Date
- Sample Call IDs

---

## Technical Notes

### Question Matching Strategy

**v1 - Exact Match:**
```python
# Normalize questions for comparison
def normalize_question(q: str) -> str:
    return q.lower().strip().rstrip('?')

# Group by normalized question
questions_by_text = defaultdict(list)
for participant in participants:
    for q in participant.questions:
        normalized = normalize_question(q)
        questions_by_text[normalized].append({
            'original': q,
            'call_id': participant.call_id,
            'name': participant.name,
            'title': participant.title,
            'account': participant.account_domain,
            'date': participant.call_date
        })
```

**v2 - Semantic Clustering (Future):**
- Use sentence embeddings (e.g., all-MiniLM-L6-v2)
- Cluster questions with cosine similarity > 0.85
- Show representative question + "and N similar variants"

### Performance Optimization

- Cache persona classification results
- Pre-compute question frequencies on data refresh
- Paginate questions list (show top 15, "Load more" button)
- Use session state to remember expanded/collapsed state

### Call Link Generation

```python
# Gong call URL format
def get_gong_url(call_id: str) -> str:
    return f"https://app.gong.io/call?id={call_id}"
```

---

## Future Enhancements (v2+)

1. **Question Trends Over Time**:
   - Line chart showing question frequency by week/month
   - Identify emerging concerns or topics

2. **Cross-Persona Questions**:
   - Questions asked by multiple persona types
   - Highlight universal concerns

3. **Sentiment Analysis**:
   - Flag questions with concern/objection tone
   - Separate "curious questions" from "blocking questions"

4. **Answer Quality Tracking**:
   - Did we answer the question well?
   - Did it lead to follow-up questions?
   - Link to win/loss outcomes

5. **Competitive Questions**:
   - Flag questions mentioning competitors
   - Group competitor-related questions

6. **Unanswered Questions**:
   - Questions we couldn't answer on the call
   - Track follow-up status

7. **Question Preparation Guide**:
   - "Before meeting with a CTO, prepare for these questions..."
   - Sales enablement resource

8. **AI-Suggested Answers**:
   - Based on historical successful answers
   - Link to best call recordings where we answered well

---

## Open Questions

1. **Question normalization**: Should we auto-clean up questions (remove filler words) in the UI, or show them as-is?
   - **Recommendation**: Show cleaned version, with tooltip showing original

2. **Sample call limit**: How many sample calls to show per question?
   - **Recommendation**: Default show 3, "See all N calls" expander

3. **Unknown persona handling**: What to do with participants who don't fit any persona?
   - **Recommendation**: Separate "Unknown" category, review patterns, refine rules

4. **Minimum threshold**: Only show questions asked N+ times?
   - **Recommendation**: v1 show all, v2 add filter "Asked 2+ times"

5. **Real-time vs batch**: Extract questions in real-time during call processing or batch?
   - **Decision**: Already integrated into CallProcessor (real-time) ✅

6. **Multiple personas per person**: Some titles span categories (e.g., "Director & Principal Engineer")
   - **Recommendation**: Use first match in priority order (DM > Influencer > User)

---

## Success Metrics

How do we know this page is valuable?

1. **Adoption**: % of reps who view persona page before calls
2. **Engagement**: Time spent on page, questions expanded
3. **Feedback**: Sales team reports better call preparation
4. **Outcomes**: Correlation between viewing persona insights and deal progression
5. **Content updates**: Product/marketing creates content addressing top questions

---

## Example Use Cases

### Use Case 1: CTO Meeting Prep
**Scenario**: Rep has upcoming call with CTO of enterprise prospect

**Action**:
1. Filter to Decision Makers persona
2. Review top 10 questions CTOs ask
3. Prepare answers and demos addressing those concerns
4. Click through to sample calls to hear how successful reps handled questions

**Outcome**: Rep feels confident, call goes smoothly, CTO's concerns addressed proactively

### Use Case 2: Product Roadmap Prioritization
**Scenario**: Product team planning Q2 roadmap

**Action**:
1. Review top questions across all personas
2. Identify gaps (questions we can't answer well → missing features)
3. Filter to "Influencers" to understand mid-level concerns
4. Export questions to CSV, share with product leadership

**Outcome**: Roadmap informed by actual customer questions, better product-market fit

### Use Case 3: Sales Enablement Content
**Scenario**: Sales enablement team creating role-specific battlecards

**Action**:
1. Filter by persona
2. Export top 20 questions per persona
3. Create FAQ documents with great answers
4. Link to best call recordings for each question

**Outcome**: Reps have persona-specific prep materials, faster ramp time

---

## UI Styling Guidelines

- **Font Awesome Icons**:
  - Decision Makers: `fa-user-tie` (👔)
  - Influencers: `fa-handshake` (🤝)
  - Users: `fa-user-gear` or `fa-code` (👨‍💻)
  - Questions: `fa-question-circle`
  - Calls: `fa-phone`
  - External link: `fa-external-link-alt`

- **Color Scheme** (match existing app):
  - Decision Makers: Blue (#3498db)
  - Influencers: Green (#2ecc71)
  - Users: Orange (#e67e22)

- **Bordered Containers**: Use `st.container(border=True)` for metric cards

- **Tables**: Use `st.dataframe()` with custom CSS for question frequency tables

- **Expandable Sections**: Use `st.expander()` for call details per question
