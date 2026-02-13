# Gong Transcript MEDDPICC Analysis Tool

## Project Overview

A Python application that retrieves Gong call transcripts, identifies discovery calls using an LLM, and scores them against the MEDDPICC sales qualification framework.

## Objectives

1. Fetch specific Gong call transcripts via Gong API
2. Use LLM to classify if a transcript is a discovery call
3. Score discovery calls on each MEDDPICC dimension (0-5 scale)
4. Calculate an overall MEDDPICC score
5. Store results with the original Gong call link

## Input Requirements

**Sales Rep Email IDs:**
- Input: Array of sales representative email addresses
- Format: `["rep1@company.com", "rep2@company.com", ...]`
- The tool will analyze calls where these sales reps were participants

**Call Filtering Criteria:**
- **Time Range**: Last 7 days from execution date
- **Participant Type**: Must include external participants (customer/prospect)
- **Rationale**: Internal-only calls are not relevant for sales qualification analysis

**Expected Output:**
- All calls matching the criteria will be analyzed
- Only discovery calls will receive MEDDPICC scores
- Non-discovery calls will be flagged as such but not scored

## MEDDPICC Framework

**MEDDPICC** stands for:
- **M**etrics - Quantifiable business outcomes the prospect wants to achieve
- **E**conomic Buyer - The person with budget authority to make the purchase decision
- **D**ecision Criteria - The formal criteria used to evaluate solutions
- **D**ecision Process - The steps and timeline for making a decision
- **P**aper Process - The legal/procurement process (contracts, compliance, etc.)
- **I**dentify Pain - The critical business pain driving the need
- **C**hampion - An internal advocate who sells on your behalf
- **C**ompetition - Understanding competitive alternatives being considered

## Functional Requirements

### 1. Gong Transcript Retrieval

**Input Criteria:**
- Accept an array of sales rep email IDs
- Fetch calls from the last 1 week (7 days from current date)
- Filter to only include calls with external participants (exclude internal-only calls)

**Process:**
- Connect to Gong API with authentication
- Query calls using:
  - Sales rep email IDs (participants filter)
  - Date range: last 7 days
  - Participant type filter: must include external participants
- Extract for each qualifying call:
  - Call transcript text
  - Call metadata (date, participants, duration)
  - Participant details (internal vs external)
  - Gong call link/URL
  - Call title/subject

### 2. Discovery Call Classification
- Use LLM to analyze transcript content
- Determine if the call is a discovery call based on:
  - Presence of needs analysis questions
  - Discussion of business challenges/pain points
  - Exploration of decision-making process
  - Qualification questions
- Return binary classification: `is_discovery_call` (True/False)

### 3. MEDDPICC Scoring (for discovery calls only)

Score each dimension on a 0-5 scale (be strict - only award high scores when criteria are clearly and explicitly met):

#### Metrics (0-5)
- **5**: Specific quantifiable metrics discussed (revenue targets, cost savings, efficiency gains with numbers)
- **3**: General metrics mentioned without specific numbers
- **2**: Business outcomes discussed but not quantified
- **0**: Vague references to improvement or success, minimal mention, or no metrics discussed

#### Economic Buyer (0-5)
- **5**: Economic buyer identified by name and title, confirmed budget authority
- **4**: Economic buyer identified, authority implied
- **3**: Discussion about who controls budget, but not confirmed
- **0**: Unclear who has budget authority, vague references, or no discussion of economic buyer

#### Decision Criteria (0-5)
- **5**: Explicit formal criteria documented (RFP, scorecard, evaluation matrix)
- **4**: Clear informal criteria discussed (must-haves, priorities)
- **2**: Some evaluation factors mentioned
- **0**: Vague references, minimal discussion, or no decision criteria discussed

#### Decision Process (0-5)
- **5**: Complete process mapped with steps, timeline, and stakeholders
- **4**: Key steps and approximate timeline identified
- **3**: Some process elements discussed
- **0**: Vague references, minimal mention, or no process discussion

#### Paper Process (0-5)
- **5**: Full procurement/legal process mapped with timeline
- **4**: Key approval steps and stakeholders identified
- **3**: Some procurement/legal requirements mentioned
- **0**: Vague references, minimal mention, or no paper process discussed

#### Identify Pain (0-5)
- **5**: Critical business pain clearly articulated with impact and urgency
- **4**: Significant pain identified with business impact
- **2**: Pain points mentioned but impact unclear
- **0**: Vague problems, minimal mention, or no clear pain identified

#### Champion (0-5)
- **5**: Champion identified, committed to advocate internally, has influence
- **4**: Champion identified and supportive
- **3**: Potential champion identified but commitment unclear
- **1**: Friendly contact but not an advocate
- **0**: Minimal engagement or no champion identified

#### Competition (0-5)
- **5**: All competitors identified, strengths/weaknesses understood
- **4**: Main competitors known with some differentiation clarity
- **3**: Some competitive alternatives mentioned
- **1**: Vague awareness or minimal mention of alternatives
- **0**: No competitive discussion

### 4. Overall Score Calculation
- Calculate average of all 8 MEDDPICC dimension scores
- Round to 1 decimal place
- Overall score range: 0.0 - 5.0

### 5. Database Schema

**Account Record** (grouped by external email domain):
```json
{
  "domain": "example.com",
  "created_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp",
  "calls": [
    {
      "call_id": "string",
      "call_date": "ISO-8601 timestamp",
      "sales_rep": "string",
      "external_participants": ["string"],
      "meddpicc_scores": {
        "metrics": integer (0-5),
        "economic_buyer": integer (0-5),
        "decision_criteria": integer (0-5),
        "decision_process": integer (0-5),
        "paper_process": integer (0-5),
        "identify_pain": integer (0-5),
        "champion": integer (0-5),
        "competition": integer (0-5),
        "overall_score": float (0.0-5.0)
      }
    }
  ],
  "overall_meddpicc": {
    "metrics": integer (0-5) - max across all calls,
    "economic_buyer": integer (0-5) - max across all calls,
    "decision_criteria": integer (0-5) - max across all calls,
    "decision_process": integer (0-5) - max across all calls,
    "paper_process": integer (0-5) - max across all calls,
    "identify_pain": integer (0-5) - max across all calls,
    "champion": integer (0-5) - max across all calls,
    "competition": integer (0-5) - max across all calls,
    "overall_score": float (0.0-5.0) - max across all calls
  }
}
```

**Notes:**
- Only discovery calls are stored in the database
- External domain is extracted from the first external participant email
- Overall MEDDPICC is calculated as the maximum score for each dimension across all discovery calls for that account
- This allows tracking MEDDPICC coverage progression across 2-3 discovery calls per account

### 6. Output Format (Per-Call Analysis)

```json
{
  "call_id": "string",
  "gong_link": "string",
  "call_date": "ISO-8601 timestamp",
  "sales_rep_email": "string",
  "participants": {
    "internal": ["string"],
    "external": ["string"]
  },
  "is_discovery_call": boolean,
  "meddpicc_scores": {
    "metrics": integer (0-5),
    "economic_buyer": integer (0-5),
    "decision_criteria": integer (0-5),
    "decision_process": integer (0-5),
    "paper_process": integer (0-5),
    "identify_pain": integer (0-5),
    "champion": integer (0-5),
    "competition": integer (0-5),
    "overall_score": float (0.0-5.0)
  },
  "analysis_notes": {
    "metrics": "string - brief explanation",
    "economic_buyer": "string - brief explanation",
    "decision_criteria": "string - brief explanation",
    "decision_process": "string - brief explanation",
    "paper_process": "string - brief explanation",
    "identify_pain": "string - brief explanation",
    "champion": "string - brief explanation",
    "competition": "string - brief explanation"
  },
  "analysis_timestamp": "ISO-8601 timestamp"
}
```

## Technical Architecture

### Components

1. **Gong API Client**
   - Authentication handler
   - Transcript fetcher
   - Rate limiting/error handling

2. **LLM Client**
   - Support for OpenAI/Anthropic APIs
   - Prompt templates for:
     - Discovery call classification
     - MEDDPICC scoring
   - Response parsing

3. **Analyzer**
   - Orchestrates the analysis workflow
   - Manages LLM calls with appropriate prompts
   - Structures output data

4. **Storage Layer (Database Integration)**
   - **Repository Pattern**: Abstract interface for multiple storage backends
   - **SQLite (Local Development)**: File-based database for local testing
   - **Firestore (Cloud Deployment)**: Scalable NoSQL for Cloud Run
   - **Account-Level Tracking**: Store discovery calls grouped by external domain
   - **MEDDPICC Aggregation**: Track maximum score for each dimension across all calls per account
   - Option to export to CSV for reporting

5. **CLI Interface**
   - Accept array of sales rep email IDs as input
   - Configuration options (API keys, output path, lookback period)
   - Batch processing support for multiple sales reps

### Technology Stack

- **Python 3.9+**
- **Libraries**:
  - `requests` - HTTP client for Gong API
  - `openai` or `anthropic` - LLM client
  - `pydantic` - Data validation and models
  - `python-dotenv` - Environment variable management
  - `click` or `argparse` - CLI framework
  - `pandas` (optional) - Data export/reporting

### Configuration

Environment variables or config file:
```
# Gong API
GONG_API_KEY=your_gong_api_key
GONG_API_URL=https://api.gong.io/v2
GONG_LOOKBACK_DAYS=7  # Number of days to look back for calls
INTERNAL_DOMAIN=yourcompany.com  # For external participant detection

# LLM
LLM_PROVIDER=anthropic
LLM_API_KEY=your_llm_api_key
LLM_MODEL=claude-haiku-4-5-20251001  # Haiku for cost optimization

# Slack (Optional - for threaded posting)
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_CHANNEL_ID=C01234567  # Channel ID to post to

# Database
DB_TYPE=sqlite  # "sqlite" for local, "firestore" for cloud
SQLITE_DB_PATH=./data/calls.db

# Output
OUTPUT_PATH=./results
```

### Example Usage

**CLI Command:**
```bash
python main.py --sales-reps john.doe@company.com jane.smith@company.com --output results/analysis.json

# Or using a config file with email list
python main.py --sales-reps-file sales_reps.txt --output results/

# Or as a Python list input
python main.py --sales-reps '["john.doe@company.com", "jane.smith@company.com", "bob.jones@company.com"]'
```

**Input File Format (sales_reps.txt):**
```
john.doe@company.com
jane.smith@company.com
bob.jones@company.com
```

## Data Flow

1. **Input**: Array of sales rep email IDs (sorted alphabetically)
2. **Query**: Search Gong API for calls matching criteria:
   - Sales reps from provided email list
   - Date range: last 7 days
   - Must have external participants
3. **Fetch**: Retrieve transcript and metadata for each qualifying call
4. **Process by Rep**: Process calls grouped by sales rep (alphabetically)
   - For each rep, open a Slack thread (if enabled)
   - Process each call for that rep
5. **Classify**: LLM determines if transcript is a discovery call
6. **Score**: If discovery call, LLM scores each MEDDPICC dimension
7. **Store**: Save to database grouped by external email domain
   - Extract domain from external participant email
   - Update account record with new call
   - Recalculate overall_meddpicc (max of each dimension)
8. **Post**: Post to Slack in real-time as each discovery call completes (if enabled)
9. **Summary**: Post completion summary for each rep and overall summary table
10. **Output**: Return/display results for all analyzed calls

## Error Handling

- API authentication failures
- Rate limiting (implement exponential backoff)
- Invalid or non-existent sales rep email addresses
- No calls found matching criteria (date range, external participants)
- LLM API errors (retry logic)
- Malformed transcripts
- Network timeouts
- Participant classification errors (unable to determine internal vs external)

## Implemented Enhancements

✅ **Database Integration (v2.0)**
- Repository pattern for portable storage (SQLite, Firestore)
- Account-level MEDDPICC tracking by external domain
- Aggregation: max score per dimension across all calls
- Tracks multiple discovery calls per account (2-3 calls typical)
- **Call deduplication**: Checks if call already evaluated (skips re-analysis)
- **Reasoning storage**: Stores analysis notes for each MEDDPICC dimension
- **Evolution tracking**: View how MEDDPICC aspects evolved across calls

✅ **Slack Integration**
- Real-time threaded posting (one thread per sales rep)
- Posts discovery calls as they complete analysis
- Per-rep completion summaries
- Overall summary table with averages

✅ **Processing Order**
- Alphabetically sorted sales reps
- Per-rep processing with grouped output

✅ **Cost Optimization**
- Skips already-evaluated calls (no redundant LLM calls)
- Idempotent: safe to re-run without re-processing
- Uses Haiku for cost-effective analysis

## Future Enhancements

- Firestore implementation for Cloud Run deployment
- Trend analysis across calls over time
- Integration with CRM systems (Salesforce, HubSpot)
- Custom scoring rubrics per team/organization
- Multi-language support for transcripts
- Confidence scores for LLM assessments
- Web dashboard for visualization
- Alerts for low-scoring discovery calls
- Historical MEDDPICC progression charts per account

## Success Metrics

- Accurate discovery call classification (>90% precision)
- Consistent MEDDPICC scoring aligned with sales team judgment
- Processing time <30 seconds per call
- Reliable API integration with error recovery
