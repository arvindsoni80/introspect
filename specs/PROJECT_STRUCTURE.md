# Project Structure

```
introspect/
├── src/                          # Source code
│   ├── __init__.py
│   ├── analyzer.py               # Main analysis orchestrator
│   ├── config.py                 # Settings and configuration
│   ├── formatters.py             # Output formatting
│   ├── gong_client.py            # Gong API client
│   ├── llm_client.py             # LLM API client (Claude)
│   ├── models.py                 # Pydantic data models
│   ├── repository.py             # Repository interface
│   ├── slack_client.py           # Slack API client
│   └── sqlite_repository.py      # SQLite implementation
│
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── README.md                 # Test documentation
│   ├── test_gong.py              # Gong API integration test
│   ├── test_llm.py               # LLM analysis test
│   └── test_db.py                # Database integration test
│
├── main.py                       # CLI entry point
├── view_db.py                    # Database viewer utility
├── view_evolution.py             # MEDDPICC evolution viewer
│
├── spec.md                       # Project specification
├── DB_QUICK_REFERENCE.md         # Database usage guide
├── EVOLUTION_TRACKING.md         # Evolution tracking guide
├── PROJECT_STRUCTURE.md          # This file
│
├── .env.example                  # Environment variables template
├── requirements.txt              # Python dependencies
├── venv/                         # Virtual environment (not in git)
├── data/                         # Database files (not in git)
└── results/                      # Output files (not in git)
```

## Import Patterns

### For modules in `src/`
```python
# Relative imports within src/
from .models import CallAnalysis
from .config import Settings
```

### For scripts in project root (main.py, view_db.py, etc.)
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from src.models import CallAnalysis
```

### For tests in `tests/`
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.models import CallAnalysis
```

## Running Commands

### Main Application
```bash
# From project root
python main.py --sales-reps your@email.com --post-slack
```

### View Database
```bash
# From project root
python view_db.py
python view_evolution.py
```

### Run Tests
```bash
# From project root
python tests/test_gong.py --sales-reps your@email.com
python tests/test_llm.py
python tests/test_db.py

# From tests directory
cd tests
python test_gong.py --sales-reps your@email.com
python test_llm.py
python test_db.py
```

## Key Files

### Entry Points
- **`main.py`** - CLI application, orchestrates the full analysis workflow
- **`view_db.py`** - View database contents with MEDDPICC scores
- **`view_evolution.py`** - View MEDDPICC evolution for multi-call accounts

### Core Logic
- **`src/analyzer.py`** - Orchestrates analysis workflow
- **`src/gong_client.py`** - Gong API integration
- **`src/llm_client.py`** - Claude LLM integration for classification and scoring
- **`src/repository.py`** - Abstract database interface
- **`src/sqlite_repository.py`** - SQLite implementation

### Data Models
- **`src/models.py`** - All Pydantic models:
  - `CallAnalysis` - Single call analysis result
  - `AccountCall` - Discovery call record for database
  - `AccountRecord` - Account with all calls and aggregated MEDDPICC
  - `MEDDPICCScores` - MEDDPICC scores (0-5 scale)
  - `AnalysisNotes` - Reasoning for each MEDDPICC dimension

### Configuration
- **`.env`** - Environment variables (create from `.env.example`)
- **`src/config.py`** - Settings loader

### Documentation
- **`spec.md`** - Complete project specification
- **`DB_QUICK_REFERENCE.md`** - Database usage guide
- **`EVOLUTION_TRACKING.md`** - Evolution tracking feature guide
- **`tests/README.md`** - Test suite documentation

## Database

### Location
- **Local**: `./data/calls.db` (SQLite)
- **Cloud**: Firestore (planned)

### Schema
- **Table**: `accounts`
- **Primary Key**: `domain` (external email domain)
- **Fields**: `created_at`, `updated_at`, `calls` (JSON), `overall_meddpicc` (JSON)

### Tools
- `python view_db.py` - View all accounts with detailed reasoning
- `python view_evolution.py` - View evolution for multi-call accounts
- `sqlite3 ./data/calls.db` - Direct SQL access
- DB Browser for SQLite - GUI tool

## Workflow

1. **Configure** - Set up `.env` with API keys
2. **Test** - Run tests to verify setup
3. **Analyze** - Run `main.py` to analyze calls
4. **View** - Use `view_db.py` or `view_evolution.py` to explore results
5. **Iterate** - Re-run safely (skips already-evaluated calls)

## Features

✅ **Gong Integration** - Fetch calls with external participants
✅ **LLM Analysis** - Claude Haiku for cost-effective classification and scoring
✅ **MEDDPICC Scoring** - 0-5 scale for 8 dimensions
✅ **Database Storage** - Track calls by account (domain)
✅ **Evolution Tracking** - See how MEDDPICC improves across calls
✅ **Call Deduplication** - Skip already-evaluated calls (cost savings)
✅ **Slack Integration** - Real-time threaded posting
✅ **Reasoning Storage** - Detailed notes for each MEDDPICC dimension
