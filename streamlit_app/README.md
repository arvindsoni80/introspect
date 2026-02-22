# Introspect Streamlit Dashboard

## Running the App

### Prerequisites

Make sure you have processed some calls first:

```bash
# From the project root
python process_calls.py --days 90 --limit 100
```

### Start the Dashboard

```bash
# From the project root
streamlit run streamlit_app/app.py
```

The app will open in your browser at `http://localhost:8501`

## Navigation

### 📊 Summary
Executive overview with two-panel comparison:
- **KPIs**: Total calls, unique accounts, sales reps, calls/rep/day, accounts/rep
- **Trends**: Daily bar charts showing call volume and account engagement
- **Filters**: Date range (7/30/90 days), Stage filter
- **Compare**: Select different segments in each panel to compare side-by-side

### 🏢 Accounts
Account-level view with deal health and scoring:
- Filter by segment and stage
- View MEDDPICC, TRIAL, and CLOSE scores
- See call history and participants
- Track qualification gaps

### 👥 Reps
Sales rep performance view:
- Compare reps across frameworks
- View strengths and weaknesses
- Track individual call activity

## Filters

All pages share common sidebar filters:
- **Date Range**: Last 7 days, Last 30 days, Last 90 days
- **Stage**: All Stages, Discovery, Trial, Negotiation, Closed

The Summary page adds independent segment selectors per panel.

## Data Requirements

The dashboard requires:
- SQLite database at path specified in `.env` (default: `introspect.db`)
- Processed calls with MEDDPICC, TRIAL, and CLOSE evaluations
- Active sales reps defined in `sales_reps` table

## Troubleshooting

**"No data available"**
- Make sure you've run `process_calls.py` to populate the database
- Check that your date range filter includes processed calls

**"Module not found: streamlit_shadcn_ui"**
- Install with: `pip install streamlit-shadcn-ui`
- The app will work without it, using native Streamlit components

**Slow loading**
- Large date ranges (90+ days) may take a few seconds to load
- Consider narrowing your date range or optimizing queries

## Development

To modify the dashboards:
1. Edit files in `streamlit_app/pages/`
2. Streamlit auto-reloads on file changes
3. Click "Rerun" in the browser if needed

## Technology Stack

- **Streamlit**: Web framework
- **Plotly**: Charts and visualizations
- **SQLite**: Data storage
- **streamlit-shadcn-ui**: UI components (optional)
