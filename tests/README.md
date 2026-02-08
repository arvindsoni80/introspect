# Test Suite

This directory contains test scripts for validating different components of the Introspect application.

## Available Tests

### 1. `test_gong.py` - Gong API Integration Test
Tests the Gong API connection and call retrieval without making LLM calls.

**What it tests:**
- Configuration loading
- Sales rep email → Gong user ID mapping
- Fetching calls with external participants
- Transcript retrieval

**Usage:**
```bash
# From project root
python tests/test_gong.py --sales-reps your@email.com

# Or with a file
python tests/test_gong.py --sales-reps-file sales_reps.txt

# From tests directory
cd tests
python test_gong.py --sales-reps your@email.com
```

**Expected output:**
- ✓ All emails mapped to user IDs
- ✓ Calls with external participants found
- ✓ Transcripts successfully fetched

### 2. `test_llm.py` - LLM Analysis Test
Tests the LLM client with sample transcripts (no Gong API calls).

**What it tests:**
- Discovery call classification
- MEDDPICC scoring
- Analysis notes generation

**Usage:**
```bash
# From project root
python tests/test_llm.py

# From tests directory
cd tests
python test_llm.py
```

**Expected output:**
- ✓ Discovery call correctly identified
- ✓ Non-discovery call correctly identified
- ✓ MEDDPICC scores generated with reasoning

**Note:** Uses sample hardcoded transcripts, so no API keys required except LLM API key.

### 3. `test_db.py` - Database Integration Test
Tests the SQLite repository with sample data.

**What it tests:**
- Database creation and initialization
- Account creation and updates
- Call storage with MEDDPICC scores
- Overall MEDDPICC aggregation (max across calls)
- Domain listing and retrieval

**Usage:**
```bash
# From project root
python tests/test_db.py

# From tests directory
cd tests
python test_db.py
```

**Expected output:**
- ✓ Creates test database at `/tmp/test_calls.db`
- ✓ Creates accounts with discovery calls
- ✓ Aggregates MEDDPICC scores correctly
- ✓ Lists and retrieves accounts

**Note:** Creates a temporary database at `/tmp/test_calls.db`. Does not affect your production database.

## Running All Tests

```bash
# From project root
python tests/test_gong.py --sales-reps your@email.com
python tests/test_llm.py
python tests/test_db.py
```

## Prerequisites

Make sure your `.env` file is configured with:
- `GONG_ACCESS_KEY` and `GONG_SECRET_KEY` (for test_gong.py)
- `LLM_API_KEY` (for test_llm.py)
- No special config needed for test_db.py

## Troubleshooting

### Import Errors
If you get `ModuleNotFoundError`, make sure you're running from the project root:
```bash
cd /path/to/introspect
python tests/test_gong.py --sales-reps your@email.com
```

### Gong API Errors
- Check your `.env` file has correct `GONG_ACCESS_KEY` and `GONG_SECRET_KEY`
- Verify the sales rep email exists in your Gong workspace
- Check network connectivity to Gong API

### LLM API Errors
- Check your `.env` file has correct `LLM_API_KEY`
- Verify you have credits/quota with Anthropic
- Check the model name in `LLM_MODEL` is correct

## Test Development

When adding new tests:
1. Create a new `test_*.py` file in this directory
2. Use the same import pattern:
   ```python
   import sys
   from pathlib import Path
   sys.path.insert(0, str(Path(__file__).parent.parent))
   from src.module_name import ClassName
   ```
3. Make it executable: `chmod +x tests/test_*.py`
4. Add shebang: `#!/usr/bin/env python3`
5. Document it in this README
