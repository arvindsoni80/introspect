# Introspect Streamlit UI

Sales coaching and account qualification dashboard for MEDDPICC analysis.

## Quick Start

### 1. Install Dependencies

From the `streamlit_app` directory:

```bash
pip install -r requirements_ui.txt
```

Or from the project root:

```bash
pip install -r streamlit_app/requirements_ui.txt
```

### 2. Run the App

From the `streamlit_app` directory:

```bash
streamlit run app.py
```

Or from the project root:

```bash
streamlit run streamlit_app/app.py
```

The app will open in your browser at `http://localhost:8501`

## Pages

The UI has 4 main pages:

1. **Home** (`app.py`) - Overview and quick stats
2. **Team Coaching** - Team-wide MEDDPICC insights and coaching priorities
3. **Rep Coaching** - Individual rep performance and coaching
4. **Account Qualification** - Account health and red flags

## Development Status

### Phase 1: Foundation ✅ COMPLETE
- ✅ Database queries (`utils/db_queries.py`)
- ✅ Metrics calculations (`utils/metrics.py`)
- ✅ Styling and formatters (`utils/styling.py`)
- ✅ Basic home page (`app.py`)

### Phase 2: Team Coaching Dashboard (In Progress)
- [ ] Team coaching page
- [ ] MEDDPICC heatmap
- [ ] Coaching priorities
- [ ] Example calls

### Phase 3: Rep Coaching Dashboard (Planned)
- [ ] Rep selector
- [ ] Rep vs team comparison
- [ ] Focus areas
- [ ] Progress tracking

### Phase 4: Account Qualification Dashboard (Planned)
- [ ] Account list with filters
- [ ] Red flag detection
- [ ] Account detail view
- [ ] Evolution charts

## Project Structure

```
streamlit_app/
├── app.py                  # Main home page
├── pages/                  # Additional pages
│   ├── 1_Team_Coaching.py
│   ├── 2_Rep_Coaching.py
│   └── 3_Account_Qualification.py
├── utils/                  # Utility modules
│   ├── __init__.py
│   ├── db_queries.py       # Database query functions
│   ├── metrics.py          # Metrics and insights
│   └── styling.py          # Colors and formatters
├── .streamlit/
│   └── config.toml         # Streamlit configuration
├── requirements_ui.txt     # UI dependencies
└── README.md               # This file
```

## Data Source

The UI reads from the SQLite database at `./data/calls.db` (configured in main `.env` file).

Make sure to run the analyzer first to populate the database:

```bash
python main.py --sales-reps your@email.com
```

## Configuration

Configuration is inherited from the main project's `.env` file:
- Database path: `SQLITE_DB_PATH`

UI-specific configuration is in `.streamlit/config.toml`:
- Theme colors
- Server settings
- Browser settings

## Troubleshooting

**"No module named 'src'"**
- The app needs to be run from the `streamlit_app/` directory or with the correct Python path

**"No accounts found in database"**
- Run the analyzer first: `python main.py --sales-reps your@email.com`

**Database locked error**
- Close any other connections to the database (DB Browser, other scripts, etc.)

**Port already in use**
- Change port in `.streamlit/config.toml` or run with: `streamlit run app.py --server.port 8502`
