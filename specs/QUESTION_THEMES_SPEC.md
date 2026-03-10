# Question Themes & Collateral Spec (Phase 2)

## Overview

Group recurring customer questions into actionable themes/topics to enable creation of sales collateral (battle cards, FAQ docs, training materials). This helps sales and marketing understand common concerns and create targeted content addressing them.

---

## Goals

1. **Identify Question Themes**: Group similar questions into meaningful categories
2. **Make Themes Actionable**: Each theme should be specific enough to create content for
3. **Enable Collateral Creation**: Export themes with sample questions, frequency, and context
4. **Persona-Specific Insights**: Show what each persona type cares about most
5. **Track Theme Evolution**: Understand how concerns change over time

---

## What is a Theme?

A **theme** is a logical grouping of related questions around a specific topic or concern.

### Theme Structure:
```json
{
  "theme_id": "pricing-enterprise",
  "theme_name": "Enterprise Pricing & Licensing",
  "theme_description": "Questions about how pricing works for large deployments, volume discounts, and licensing models",
  "persona": "Decision Maker",
  "question_count": 47,
  "questions": [
    {
      "question": "What's your pricing model for enterprise deployments?",
      "frequency": 12,
      "sample_calls": ["call_id_1", "call_id_2", "call_id_3"]
    },
    {
      "question": "Do you offer volume discounts?",
      "frequency": 8,
      "sample_calls": ["call_id_4", "call_id_5"]
    }
  ],
  "suggested_collateral": [
    "Enterprise pricing one-pager",
    "Volume licensing FAQ",
    "ROI calculator"
  ],
  "last_updated": "2026-02-24T10:30:00Z"
}
```

---

## Theme Categories (Examples)

We expect themes to emerge naturally from the data, but common categories might include:

### Decision Maker Themes:
- **Pricing & Commercial**: Pricing models, contracts, licensing, discounts
- **ROI & Business Value**: Cost savings, productivity gains, business outcomes
- **Risk & Compliance**: Security, SOC 2, GDPR, data handling
- **Vendor Evaluation**: Company stability, customer base, funding
- **Strategic Fit**: Roadmap alignment, vision, market positioning

### Influencer Themes:
- **Implementation & Onboarding**: Setup time, migration effort, rollout strategy
- **Team Enablement**: Training, documentation, support resources
- **Technical Integration**: API availability, SSO, existing tool compatibility
- **Customization & Flexibility**: Configuration options, workflow adaptation
- **Proof Points**: Case studies, references, success metrics

### User Themes:
- **Day-to-Day Usability**: Interface, workflow, learning curve
- **Feature Functionality**: Specific capabilities, limitations, edge cases
- **Performance & Reliability**: Speed, uptime, error handling
- **Developer Experience**: CLI, IDE plugins, keyboard shortcuts
- **Troubleshooting**: Common issues, debugging, getting help

---

## Categorization Approaches

### Option 1: LLM-Based Thematic Analysis (Recommended for v1)

**How it works:**
1. For each persona, take all unique questions (with frequency)
2. Send to LLM with prompt: "Analyze these questions and group them into 5-8 themes"
3. LLM returns:
   - Theme names
   - Theme descriptions
   - Question assignments
   - Suggested collateral types

**Prompt Example:**
```
You are analyzing customer questions from sales calls. Group these questions into 5-8 logical themes.

QUESTIONS (with frequency):
1. "What's your pricing model?" (asked 12 times)
2. "Do you offer volume discounts?" (asked 8 times)
3. "How does this integrate with Jira?" (asked 15 times)
4. "What's the implementation timeline?" (asked 10 times)
...

For each theme, provide:
- Theme name (short, 2-5 words)
- Description (1 sentence)
- Which questions belong to this theme
- Suggested collateral types (battle cards, FAQs, one-pagers, etc.)

Return as JSON...
```

**Pros:**
- Simple to implement
- Generates human-readable themes
- Provides collateral suggestions
- Can refine with better prompts

**Cons:**
- Costs $ per analysis (~$0.01-0.05 depending on question count)
- Need to re-run when new questions added
- May group differently each time (non-deterministic)

---

### Option 2: Embedding-Based Clustering + LLM Naming

**How it works:**
1. Generate embeddings for each question (e.g., sentence-transformers)
2. Cluster questions using cosine similarity (k-means, DBSCAN, hierarchical)
3. For each cluster, use LLM to:
   - Generate theme name
   - Write theme description
   - Suggest collateral

**Pros:**
- More consistent clustering (deterministic)
- Handles semantic similarity well
- Fast after initial embedding generation

**Cons:**
- More complex implementation
- Need embedding model (can use OpenAI, Anthropic, or local model)
- Still need LLM for naming (adds cost)

---

### Option 3: Manual Theme Definition + Auto-Assignment

**How it works:**
1. Define themes manually based on common patterns
2. Use LLM to assign each question to a theme
3. Track unassigned questions, refine themes over time

**Pros:**
- Controlled theme taxonomy
- Consistent across time
- Can align with existing content strategy

**Cons:**
- Requires upfront manual work
- May miss emergent themes
- Rigid - doesn't adapt to new patterns

---

## Recommendation: Start with Option 1

**Why:**
- Fastest to implement
- Requires no manual theme definition
- Adapts to your actual question patterns
- Good enough for v1

**Refinement path:**
- v1: LLM generates themes fresh each time
- v2: Cache themes, only re-cluster monthly
- v3: Add embedding-based clustering for consistency

---

## Storage Strategy

### Option A: Store in Database (Recommended)

Create a new table to store themes:

```sql
CREATE TABLE question_themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    persona TEXT NOT NULL,
    theme_name TEXT NOT NULL,
    theme_description TEXT,
    suggested_collateral TEXT, -- JSON array
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),

    UNIQUE(persona, theme_name)
);

CREATE TABLE question_theme_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_id INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    frequency INTEGER NOT NULL,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (theme_id) REFERENCES question_themes(id),
    UNIQUE(theme_id, question_text)
);
```

**Pros:**
- Persistent storage
- Can query/filter themes
- Can track theme evolution over time

**Cons:**
- Requires migration
- Need to manage staleness/refresh

---

### Option B: Compute On-the-Fly (Simpler for v1)

Don't store themes - generate them when viewing the Persona page.

**Pros:**
- No schema changes
- Always current
- Simple to start

**Cons:**
- Slow page load (LLM call takes 5-15 seconds)
- Costs money on every page view
- May generate different themes each time

---

### Recommendation: Option B for v1, Option A for v2

Start with on-the-fly generation to validate the approach. Once we're happy with theme quality, add database storage and refresh strategy.

---

## UI Changes (Persona Page)

### Current (Phase 1):
```
[Persona Tabs]
  → List of questions with frequency
  → Expandable call details
```

### Proposed (Phase 2):
```
[Persona Tabs]
  → [View: Themes / Raw Questions] toggle

  === Themes View ===

  Theme 1: Enterprise Pricing & Licensing (47 questions)
    Description: Questions about pricing models, volume discounts, and licensing
    Suggested Collateral: Enterprise pricing one-pager, Volume licensing FAQ

    Top Questions:
      1. What's your pricing model for enterprise deployments? (12x)
      2. Do you offer volume discounts? (8x)
      3. How does licensing work for contractors? (6x)

    [See all 47 questions in this theme]
    [Export theme as FAQ template]

  Theme 2: Security & Compliance (38 questions)
    ...

  === Raw Questions View ===
  (Same as current Phase 1 - flat list)
```

---

## Collateral Export Formats

Once themes are identified, enable export in formats useful for creating collateral:

### 1. FAQ Template (Markdown)
```markdown
# Enterprise Pricing & Licensing FAQ

## What's your pricing model for enterprise deployments?

[Placeholder for answer]

**Asked by**: Decision Makers (12 times)
**Sample calls**: Capital One (2/10), Visa (2/8), HP (2/5)

---

## Do you offer volume discounts?

[Placeholder for answer]

**Asked by**: Decision Makers (8 times)
**Sample calls**: Cisco (2/12), KPMG (2/9)
```

### 2. Battle Card (JSON for design tools)
```json
{
  "title": "Enterprise Pricing & Licensing",
  "persona": "Decision Maker",
  "top_questions": [
    "What's your pricing model for enterprise deployments?",
    "Do you offer volume discounts?",
    "How does licensing work for contractors?"
  ],
  "talking_points": [
    "[Placeholder: Volume-based pricing tiers]",
    "[Placeholder: Enterprise license includes...]",
    "[Placeholder: Contractor seat flexibility]"
  ],
  "proof_points": [
    "[Placeholder: Avg 40% cost savings vs competitor]",
    "[Placeholder: Fortune 500 customers]"
  ]
}
```

### 3. Sales Enablement Report (CSV)
```csv
Theme,Persona,Question,Frequency,Accounts,Sample Calls
Enterprise Pricing,Decision Maker,"What's your pricing model?",12,"Capital One, Visa, HP","call_id_1, call_id_2"
Enterprise Pricing,Decision Maker,"Do you offer volume discounts?",8,"Cisco, KPMG","call_id_3, call_id_4"
```

---

## Refresh Strategy

**Question**: How often should we re-generate themes?

### Option 1: Manual Refresh
- Add "Regenerate Themes" button in UI
- Admin clicks to refresh themes with latest data
- Shows "Last updated: 3 days ago"

**Pros**: Simple, controlled
**Cons**: Can get stale

### Option 2: Scheduled Refresh
- Re-generate themes nightly or weekly
- Background job updates database

**Pros**: Always current
**Cons**: Costs money, themes may change unexpectedly

### Option 3: Incremental Refresh
- When new questions added, check if they fit existing themes
- If not, trigger re-clustering

**Pros**: Adaptive
**Cons**: Complex logic

**Recommendation**: Start with **Option 1 (Manual Refresh)** for v1.

---

## LLM Prompt Strategy

### Theme Generation Prompt (v1):

```
You are analyzing customer questions from sales calls with [PERSONA] stakeholders.

Your task: Group these questions into 5-8 logical themes that would be useful for creating sales collateral.

QUESTIONS (with frequency):
{question_list}

INSTRUCTIONS:
1. Identify 5-8 themes that naturally emerge from these questions
2. Each theme should be specific enough to create a battle card or FAQ for
3. Group related questions under each theme
4. Suggest 2-3 types of collateral that would address this theme

OUTPUT FORMAT (JSON):
{
  "themes": [
    {
      "theme_name": "Short name (2-5 words)",
      "description": "One sentence explaining what this theme covers",
      "questions": [
        {
          "question": "Full question text",
          "frequency": 12
        }
      ],
      "suggested_collateral": [
        "Battle card: Enterprise Pricing",
        "FAQ: Volume Licensing",
        "One-pager: ROI Calculator"
      ]
    }
  ]
}

IMPORTANT:
- Every question must be assigned to exactly one theme
- Theme names should be actionable (e.g., "Enterprise Pricing" not "Money Stuff")
- Collateral suggestions should be specific (e.g., "SOC 2 Compliance FAQ" not "Security Doc")

Return ONLY valid JSON.
```

---

## Success Metrics

How do we know themes are useful?

1. **Coverage**: Do themes cover 95%+ of questions?
2. **Coherence**: Do questions within a theme actually relate to each other?
3. **Actionability**: Can we create collateral from theme descriptions?
4. **Adoption**: Do sales/marketing teams actually use theme-based content?
5. **Consistency**: Do themes remain stable over time (not changing dramatically week-to-week)?

---

## Open Questions

### 1. How many themes per persona?
**Options**: Fixed (always 5-8) vs Dynamic (as many as needed)
**Recommendation**: Start with 5-8, see if it feels right

### 2. Should themes be shared across personas?
**Example**: "Security & Compliance" might be asked by DMs, Influencers, AND Users
**Options**:
- A) Separate themes per persona (may have duplicates)
- B) Shared themes, track which personas ask them
**Recommendation**: Start with **A (separate)** for simplicity

### 3. How do we handle outlier questions?
Questions that don't fit any theme.
**Options**:
- Create "Miscellaneous" theme
- Leave unassigned, show separately
- Force LLM to assign to closest theme
**Recommendation**: Create **"Other Questions"** theme as catch-all

### 4. Do we track theme trends over time?
**Example**: "Pricing" questions increasing, "Security" questions decreasing
**Recommendation**: Not for v1, but good for v2

### 5. Should we let users manually adjust themes?
Allow editing theme names, reassigning questions, merging/splitting themes
**Recommendation**: Not for v1 (fully automated), consider for v2

---

## Implementation Phases

### Phase 2a (MVP - Theme Generation)
- Add "Generate Themes" button to Persona page
- Call LLM to generate themes on-demand
- Display themes in expandable sections above raw questions
- No database storage (compute on-the-fly)

**Effort**: 1-2 days
**Value**: Immediate insight into question patterns

### Phase 2b (Theme Export)
- Add export buttons per theme
- Generate FAQ templates (Markdown)
- Generate battle card templates (JSON)
- Generate CSV for spreadsheet analysis

**Effort**: 1 day
**Value**: Enables collateral creation

### Phase 2c (Theme Persistence)
- Add question_themes and question_theme_assignments tables
- Store themes in database
- Add "Refresh Themes" button
- Show "Last updated" timestamp

**Effort**: 1-2 days
**Value**: Faster page loads, consistent themes

### Phase 2d (Advanced Features)
- Theme trend tracking over time
- Cross-persona theme analysis
- Embedding-based clustering for consistency
- Manual theme editing UI

**Effort**: 3-5 days
**Value**: Advanced insights

---

## Example Output

**Scenario**: Decision Maker questions from last 30 days

**Generated Themes**:

1. **Enterprise Pricing & Licensing** (47 questions)
   - "What's your pricing model for enterprise deployments?" (12x)
   - "Do you offer volume discounts?" (8x)
   - "How does licensing work for contractors?" (6x)
   - Suggested: Enterprise pricing one-pager, Volume licensing FAQ

2. **Security & Compliance** (38 questions)
   - "Do you have SOC 2 compliance?" (15x)
   - "How do you handle data encryption?" (9x)
   - "What's your GDPR compliance story?" (7x)
   - Suggested: Security battle card, Compliance FAQ, Trust center link

3. **Implementation Timeline & Effort** (31 questions)
   - "What's the implementation timeline?" (10x)
   - "How much engineering effort is required?" (8x)
   - "Do you provide professional services?" (6x)
   - Suggested: Implementation guide, Services overview, Timeline estimator

4. **ROI & Business Value** (24 questions)
   - "What cost savings have other customers seen?" (8x)
   - "How do you measure ROI?" (6x)
   - "Can you share productivity metrics?" (5x)
   - Suggested: ROI calculator, Case studies, Value framework

5. **Customer References & Proof Points** (19 questions)
   - "Can you share customer references in financial services?" (7x)
   - "Who are your largest customers?" (5x)
   - "Do you have case studies?" (4x)
   - Suggested: Reference list, Case study library, Customer logos

---

## Next Steps (After Spec Approval)

1. **Implement Phase 2a (MVP)**:
   - Create theme generation service with LLM
   - Add "Generate Themes" button to UI
   - Display themes in Persona page

2. **Test with real data**:
   - Run on actual question set
   - Validate theme quality
   - Refine prompt based on results

3. **Iterate**:
   - Adjust number of themes (5-8 or dynamic?)
   - Improve theme naming
   - Add export functionality

4. **Plan Phase 2b-2d** based on feedback
