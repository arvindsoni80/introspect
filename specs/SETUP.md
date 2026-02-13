# Setup and Testing Guide

## Step 1: Configure Environment

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your credentials:**
   ```bash
   # Gong API Configuration
   GONG_API_URL=https://us-12345-api.gong.io  # Your Gong API endpoint
   GONG_ACCESS_KEY=your_access_key_here
   GONG_SECRET_KEY=your_secret_key_here
   GONG_LOOKBACK_DAYS=7
   INTERNAL_DOMAIN=yourcompany.com  # e.g., coderabbit.ai

   # LLM Configuration (not needed for Gong testing)
   LLM_PROVIDER=anthropic
   LLM_API_KEY=your_anthropic_api_key_here
   LLM_MODEL=claude-3-5-sonnet-20241022

   # Output Configuration
   OUTPUT_PATH=./results
   ```

3. **Get your Gong API credentials:**
   - Log into Gong
   - Go to Settings → Ecosystem → API
   - Create new API credentials (Access Key + Secret Key)
   - Copy your API endpoint URL (format: `https://us-XXXXX-api.gong.io`)

## Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 3: Test Gong Integration

Test the Gong API connection WITHOUT needing LLM implementation:

```bash
python test_gong.py sales_rep1@company.com sales_rep2@company.com
```

**Replace with your actual sales rep email addresses!**

### What the test does:

1. ✓ Loads your configuration
2. ✓ Tests Gong API authentication
3. ✓ Maps sales rep emails to Gong user IDs
4. ✓ Fetches calls from last 7 days
5. ✓ Filters for calls with external participants
6. ✓ Shows call details and participants
7. ✓ Fetches a sample transcript

### Example output:

```
============================================================
Testing Gong API Connection
============================================================

1. Loading configuration...
   ✓ Config loaded
   - API URL: https://us-12345-api.gong.io
   - Lookback days: 7
   - Internal domain: coderabbit.ai

2. Connecting to Gong API...
   Sales reps to check: john@coderabbit.ai

3. Testing authentication (listing users)...
   ✓ Successfully fetched 45 Gong users

4. Mapping sales rep emails to Gong user IDs...
   ✓ Found 1 matching users:
     - john@coderabbit.ai → 8472649283746

5. Fetching calls from last 7 days...
   ✓ Found 12 calls with external participants

6. Call Details:
   --------------------------------------------------------

   Call #1:
     ID: 8473829374829
     Title: Discovery Call with Acme Corp
     Date: 2026-02-05T14:30:00Z
     Sales Rep: john@coderabbit.ai
     Internal: 2 participants
     External: 3 participants
       External emails: prospect@acme.com, cto@acme.com
     Gong Link: https://app.gong.io/call?id=8473829374829

   ... (more calls)

7. Testing transcript fetch (first call)...
   ✓ Successfully fetched transcript
   - Length: 45832 characters
   - Preview (first 200 chars):
     [Speaker 1]: Hi everyone, thanks for joining today. I wanted to start by understanding your current challenges with code review...

============================================================
✓ All Gong API tests passed!
============================================================
```

## Step 4: Put Sales Rep Emails

You have two options:

### Option A: Command Line
```bash
python test_gong.py john@company.com jane@company.com
```

### Option B: File (for many emails)
1. Create a file called `sales_reps.txt`:
   ```
   john.doe@company.com
   jane.smith@company.com
   bob.jones@company.com
   ```

2. Later when LLM is implemented, use:
   ```bash
   python main.py --sales-reps-file sales_reps.txt
   ```

## Troubleshooting

### "No matching Gong users found"
- Check that email addresses exactly match what's in Gong
- The test will show you available users in Gong

### "Authentication failed"
- Verify your `GONG_ACCESS_KEY` and `GONG_SECRET_KEY` are correct
- Check that your `GONG_API_URL` is correct (get it from Gong settings)

### "No calls found"
- Sales reps might not have had calls in the last 7 days
- Calls might be internal-only (no external participants)
- Try increasing `GONG_LOOKBACK_DAYS` in `.env`

## Next Steps

Once Gong testing passes:
1. Implement LLM prompts in `src/llm_client.py`
2. Run full analysis: `python main.py --sales-reps email@company.com`
