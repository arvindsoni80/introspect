# Introspect - Gong MEDDPICC Analysis Tool

Automated analysis of Gong call transcripts using AI to score discovery calls on the MEDDPICC sales qualification framework.

## Overview

Introspect analyzes your Gong sales calls to:
- ✅ Identify discovery calls automatically
- ✅ Score each call on MEDDPICC dimensions (0-5 scale)
- ✅ Track MEDDPICC coverage across multiple calls per account
- ✅ Store results in a database with evolution tracking
- ✅ Post real-time updates to Slack (optional)
- ✅ Skip already-analyzed calls (cost optimization)

### What is MEDDPICC?

**MEDDPICC** is a sales qualification framework:
- **M**etrics - Quantifiable business outcomes
- **E**conomic Buyer - Budget authority holder
- **D**ecision Criteria - Evaluation criteria
- **D**ecision Process - Steps and timeline
- **P**aper Process - Legal/procurement process
- **I**dentify Pain - Critical business pain
- **C**hampion - Internal advocate
- **C**ompetition - Competitive alternatives

## Prerequisites

- **Python 3.9+** (Python 3.13 recommended)
- **Gong account** with API access
- **Anthropic API key** (Claude)
- **Slack workspace** (optional, for posting results)

## Installation

### 1. Clone the Repository

```bash
git clone git@github.com:arvindsoni80/introspect.git
cd introspect
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Gong API Configuration
GONG_API_URL=https://us-XXXX-api.gong.io  # Your Gong API URL
GONG_ACCESS_KEY=your_gong_access_key_here
GONG_SECRET_KEY=your_gong_secret_key_here
GONG_LOOKBACK_DAYS=7                       # Days to look back for calls
INTERNAL_DOMAIN=yourcompany.com            # Your company email domain

# LLM Configuration
LLM_PROVIDER=anthropic
LLM_API_KEY=your_anthropic_api_key_here
LLM_MODEL=claude-haiku-4-5-20251001       # Haiku for cost optimization

# Slack Configuration (Optional - for threaded posting)
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_CHANNEL_ID=C01234567                # Channel ID to post to

# Database Configuration
DB_TYPE=sqlite                             # "sqlite" for local
SQLITE_DB_PATH=./data/calls.db
```

#### Getting API Keys

**Gong API:**
1. Go to Gong Settings → Integrations → API
2. Generate Access Key and Secret Key
3. Note your API URL (format: `https://us-XXXX-api.gong.io`)

**Anthropic API:**
1. Visit https://console.anthropic.com/
2. Sign up or log in
3. Go to API Keys and create a new key

**Slack Bot (Optional):**
1. Create a Slack App: https://api.slack.com/apps
2. Add Bot Token Scopes: `chat:write`, `chat:write.public`
3. Install app to workspace
4. Copy Bot User OAuth Token (starts with `xoxb-`)
5. Get channel ID: Right-click channel → View channel details

## Testing

Before running the full analysis, test your setup:

### Test 1: Gong API Connection

```bash
python tests/test_gong.py --sales-reps your.email@company.com
```

**Expected output:**
```
✓ All emails mapped to user IDs
✓ Calls with external participants found
✓ Transcripts successfully fetched
```

### Test 2: LLM Analysis

```bash
python tests/test_llm.py
```

**Expected output:**
```
✓ Discovery call correctly identified
✓ MEDDPICC scores generated
```

### Test 3: Database Integration

```bash
python tests/test_db.py
```

**Expected output:**
```
✓ Database created
✓ Accounts stored with MEDDPICC scores
```

## Usage

### Basic Usage

Analyze calls for specific sales reps:

```bash
python main.py --sales-reps john.doe@company.com jane.smith@company.com
```

### Using a File with Multiple Sales Reps

Create a file `sales_reps.txt`:
```
john.doe@company.com
jane.smith@company.com
bob.jones@company.com
```

Run:
```bash
python main.py --sales-reps-file sales_reps.txt
```

### With Slack Posting

Post results to Slack in real-time:

```bash
python main.py --sales-reps-file sales_reps.txt --post-slack
```

**Slack output:**
- One thread per sales rep
- Each discovery call posted as it completes
- Completion summary per rep
- Overall summary table at the end

## Viewing Results

### 1. Database Viewer (Recommended)

View all accounts with detailed MEDDPICC scores and reasoning:

```bash
python view_db.py
```

**Sample output:**
```
1. acme.com
   Created:  2025-01-15 10:00:00
   Calls:    2 discovery call(s)

   📈 Overall MEDDPICC (max across all calls):
      • Metrics:           4/5
      • Economic Buyer:    4/5
      • Champion:          4/5
      ...

   📞 Discovery Calls:
      1. call-001 (2025-01-15)
         Score: 3.0/5.0
         Summary: Good pain identification, needs economic buyer clarity

         MEDDPICC Breakdown:
           • Metrics [3/5]: Discussed ROI expectations
           • Economic Buyer [2/5]: Only spoke with director level
           ...
```

### 2. Evolution Viewer

View how MEDDPICC evolved for accounts with multiple calls:

```bash
python view_evolution.py
```

**Sample output:**
```
🏢 acme.com
Total Discovery Calls: 2

Call Date    Call ID      M   EB  DC  DP  PP  IP  CH  CO  Overall
─────────────────────────────────────────────────────────────────
2025-01-15   call-001     3   2   4   3   2   5   3   2   3.00
2025-01-20   call-002     4   4   4   4   3   4   4   3   3.75

📊 Dimension Evolution:
   ✨ Metrics: 3 → 4 (improved by 1)
   ✨ Economic Buyer: 2 → 4 (improved by 2)
   ✨ Champion: 3 → 4 (improved by 1)
```

### 3. Direct Database Access

Using SQLite command line:

```bash
sqlite3 ./data/calls.db

# List all accounts
SELECT domain, updated_at FROM accounts;

# View account details
SELECT * FROM accounts WHERE domain = 'acme.com';

# Exit
.quit
```

Or use a GUI tool like [DB Browser for SQLite](https://sqlitebrowser.org/).

## How It Works

### Workflow

1. **Fetch Calls** - Retrieves calls from Gong API (last 7 days, with external participants)
2. **Check Database** - Skips already-analyzed calls (cost savings)
3. **Classify** - LLM determines if call is a discovery call
4. **Score** - If discovery, scores each MEDDPICC dimension (0-5)
5. **Store** - Saves to database, grouped by external email domain
6. **Aggregate** - Calculates overall MEDDPICC (max per dimension across calls)
7. **Post** - Optionally posts to Slack in real-time

### Processing Order

- Sales reps processed **alphabetically**
- Each rep gets a **dedicated Slack thread**
- Results posted **as each call completes** (real-time)
- Database updated **immediately** (no file writes)

### Call Deduplication

Once a call is analyzed, it's stored in the database with:
- MEDDPICC scores
- Analysis reasoning for each dimension
- Summary

On subsequent runs, the system:
- ✅ Checks if `call_id` exists in database
- ⏭️ Skips already-analyzed calls (no LLM calls)
- 💰 Saves costs and time

**Example:**
```
First run:  100 calls → All analyzed → $X cost
Second run: 110 calls → 10 new analyzed → $0.1X cost (90% savings!)
```

## Cost Optimization

### Model Choice
Uses **Claude Haiku 4.5** by default:
- Fast inference (~1-2 seconds per call)
- Low cost (~$0.001 per call)
- High accuracy for structured tasks

### Deduplication
- Skips already-analyzed calls automatically
- Safe to re-run daily without re-processing historical calls

### Estimated Costs
- Discovery classification: ~$0.0005 per call
- MEDDPICC scoring: ~$0.001 per call
- **Total: ~$0.0015 per discovery call**

Example: 100 discovery calls = ~$0.15

## Troubleshooting

### Issue: "No calls found with external participants"

**Solutions:**
- Check `GONG_LOOKBACK_DAYS` - increase if needed
- Verify sales rep email exists in Gong
- Check that calls have external participants (customers/prospects)

### Issue: "No matching Gong users found"

**Solutions:**
- Verify sales rep email matches exactly in Gong
- Run test to see available users:
  ```bash
  python tests/test_gong.py --sales-reps your@email.com
  ```

### Issue: "Anthropic API error"

**Solutions:**
- Check `LLM_API_KEY` is correct
- Verify you have credits with Anthropic
- Check rate limits (Haiku has high limits)

### Issue: "Slack posting not working"

**Solutions:**
- Verify `SLACK_BOT_TOKEN` starts with `xoxb-`
- Check bot has `chat:write` permission
- Verify `SLACK_CHANNEL_ID` is correct (not channel name)
- Make sure bot is invited to the channel

### Issue: "Module not found" errors

**Solutions:**
- Activate virtual environment: `source venv/bin/activate`
- Reinstall requirements: `pip install -r requirements.txt`
- Check Python version: `python --version` (need 3.9+)

### Issue: "Database locked"

**Solutions:**
- Close any open database connections
- Close DB Browser or other GUI tools
- Restart the analyzer

## Project Structure

```
introspect/
├── src/                    # Source code
│   ├── analyzer.py         # Main orchestrator
│   ├── gong_client.py      # Gong API integration
│   ├── llm_client.py       # Claude LLM client
│   ├── slack_client.py     # Slack integration
│   ├── repository.py       # Database interface
│   └── sqlite_repository.py # SQLite implementation
│
├── tests/                  # Test suite
│   ├── test_gong.py        # Gong API test
│   ├── test_llm.py         # LLM analysis test
│   └── test_db.py          # Database test
│
├── main.py                 # CLI entry point
├── view_db.py              # Database viewer
├── view_evolution.py       # Evolution tracker
│
├── .env                    # Your configuration (not in git)
├── .env.example            # Configuration template
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Advanced Usage

### Custom Lookback Period

Analyze calls from the last 30 days:

```bash
# Edit .env
GONG_LOOKBACK_DAYS=30

# Run analyzer
python main.py --sales-reps-file sales_reps.txt
```

### Query Database

Find accounts with low Economic Buyer scores:

```bash
sqlite3 ./data/calls.db
```

```sql
SELECT
    domain,
    json_extract(overall_meddpicc, '$.economic_buyer') as eb_score
FROM accounts
WHERE CAST(json_extract(overall_meddpicc, '$.economic_buyer') AS INTEGER) <= 2
ORDER BY eb_score;
```

### Export to CSV

```bash
sqlite3 -header -csv ./data/calls.db \
  "SELECT domain,
          json_extract(overall_meddpicc, '$.overall_score') as score,
          updated_at
   FROM accounts
   ORDER BY score DESC" > accounts.csv
```

## Best Practices

### 1. Run Daily
```bash
# Safe to run daily - skips already-analyzed calls
python main.py --sales-reps-file sales_reps.txt --post-slack
```

### 2. Review Evolution Weekly
```bash
# Check account progression
python view_evolution.py
```

### 3. Backup Database
```bash
# Create daily backup
cp ./data/calls.db ./data/calls_backup_$(date +%Y%m%d).db
```

### 4. Monitor Low Scores
Look for:
- Economic Buyer scores < 3 (need executive engagement)
- Champion scores < 3 (need internal advocate)
- Competition scores < 3 (need competitive positioning)

### 5. Sales Coaching
- Review analysis notes for each call
- Identify patterns in high vs low scoring calls
- Use as coaching tool for discovery skills

## Features

✅ **Automated Discovery Call Detection** - AI classifies calls
✅ **MEDDPICC Scoring** - 0-5 scale, 8 dimensions
✅ **Account-Level Tracking** - Grouped by customer domain
✅ **Evolution Tracking** - See progression across calls
✅ **Deduplication** - Skip analyzed calls (cost savings)
✅ **Real-Time Slack Updates** - Threaded posts as analysis completes
✅ **Detailed Reasoning** - Understand why scores were assigned
✅ **Database Storage** - Query and analyze trends
✅ **Cost Optimized** - Uses Claude Haiku (~$0.0015/call)

## Roadmap

- [ ] Firestore support (for Cloud Run deployment)
- [ ] CRM integration (Salesforce, HubSpot)
- [ ] Web dashboard for visualization
- [ ] Historical trend charts
- [ ] Custom scoring rubrics per team
- [ ] Multi-language support
- [ ] Confidence scores for assessments
- [ ] Automated coaching recommendations

## Documentation

- **README.md** (this file) - Getting started guide
- **spec.md** - Complete technical specification
- **DB_QUICK_REFERENCE.md** - Database usage guide
- **EVOLUTION_TRACKING.md** - Evolution tracking guide
- **PROJECT_STRUCTURE.md** - Project layout and patterns
- **tests/README.md** - Test suite documentation

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Review the documentation files listed above
- Check the troubleshooting section

## License

MIT
