"""Reps Dashboard - Compare sales rep performance and identify coaching opportunities."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Add pages directory to path for cross-page imports
pages_dir = Path(__file__).parent
sys.path.insert(0, str(pages_dir))

from src.core import Config
from src.data import Database, Repository

# Page config
st.set_page_config(
    page_title="Reps - Introspect",
    page_icon="👥",
    layout="wide"
)


# ============================================================================
# Constants & Helpers
# ============================================================================

def format_date(dt: datetime) -> str:
    """Format datetime for display."""
    if dt is None:
        return "N/A"
    return dt.strftime("%b %d, %Y")


def format_gong_link(call_id: str) -> str:
    """Format Gong call link."""
    return f"https://us-35231.app.gong.io/call?id={call_id}"


def get_score_emoji(score: float) -> str:
    """Get emoji based on score."""
    if score >= 4.0:
        return "🟢"
    elif score >= 2.5:
        return "🟡"
    else:
        return "🔴"


# ============================================================================
# Data Loading & Aggregation
# ============================================================================

def load_rep_performance(repo: Repository, segment: Optional[str] = None, stage: Optional[str] = None,
                         date_from: Optional[datetime] = None, date_to: Optional[datetime] = None) -> List[Dict]:
    """Load and aggregate rep performance data."""
    # Load all active sales reps
    all_reps = repo.list_sales_reps(active_only=True)

    # Filter by segment if specified
    if segment and segment != "All":
        all_reps = [r for r in all_reps if r.segment and r.segment.lower() == segment.lower()]

    # Load all accounts for win/loss calculation
    all_accounts = repo.list_accounts()
    accounts_by_id = {a.id: a for a in all_accounts}

    # Build query for calls with filters
    query_parts = ["SELECT * FROM calls WHERE 1=1"]
    params = []

    # Stage filter
    if stage and stage != "All":
        query_parts.append("AND primary_stage = ?")
        params.append(stage.lower())

    # Date range filter
    if date_from:
        query_parts.append("AND call_date >= ?")
        params.append(date_from)
    if date_to:
        query_parts.append("AND call_date <= ?")
        params.append(date_to)

    query = " ".join(query_parts)
    cursor = repo.conn.execute(query, params)
    all_calls = cursor.fetchall()

    # Aggregate data by rep
    rep_data = {}

    for rep in all_reps:
        rep_email = rep.email

        # Get calls for this rep
        rep_calls = [c for c in all_calls if c['sales_rep_email'] == rep_email]

        if not rep_calls:
            continue

        # Get unique accounts for this rep
        account_ids = set(c['account_id'] for c in rep_calls)

        # Calculate scores by stage
        discovery_scores = []
        trial_scores = []
        negotiation_scores = []

        for call_row in rep_calls:
            call = repo._row_to_call(call_row)
            call_stage = call.primary_stage

            if call_stage == "discovery":
                scores = repo.get_call_meddpicc_scores(call.call_id)
                if scores:
                    discovery_scores.append(scores.scores.overall_score)
            elif call_stage == "trial":
                scores = repo.get_call_trial_scores(call.call_id)
                if scores:
                    trial_scores.append(scores.scores.overall_score)
            elif call_stage == "negotiation":
                scores = repo.get_call_close_scores(call.call_id)
                if scores:
                    negotiation_scores.append(scores.scores.overall_score)

        # Calculate win rate (for this rep's accounts)
        rep_accounts = [accounts_by_id[aid] for aid in account_ids if aid in accounts_by_id]
        closed_accounts = [a for a in rep_accounts if a.current_stage == "closed"]

        won_accounts = 0
        for account in closed_accounts:
            # Check if won or lost
            query = """
                SELECT * FROM calls
                WHERE account_id = ? AND primary_stage = 'closed'
                ORDER BY call_date DESC
                LIMIT 1
            """
            cursor = repo.conn.execute(query, (account.id,))
            row = cursor.fetchone()
            if row:
                call = repo._row_to_call(row)
                analysis = repo.get_call_win_loss_analysis(call.call_id)
                if analysis and analysis.analysis.outcome == "won":
                    won_accounts += 1

        win_rate = (won_accounts / len(closed_accounts) * 100) if closed_accounts else None

        # Count active deals (not closed)
        active_accounts = [a for a in rep_accounts if a.current_stage != "closed"]

        # Count at-risk deals (trial or negotiation with low scores)
        at_risk_count = 0
        for account in active_accounts:
            if account.current_stage in ["trial", "negotiation"]:
                # Get most recent call for this stage
                query = """
                    SELECT * FROM calls
                    WHERE account_id = ? AND primary_stage = ?
                    ORDER BY call_date DESC
                    LIMIT 1
                """
                cursor = repo.conn.execute(query, (account.id, account.current_stage))
                row = cursor.fetchone()
                if row:
                    call = repo._row_to_call(row)
                    score = None
                    if account.current_stage == "trial":
                        scores = repo.get_call_trial_scores(call.call_id)
                        if scores:
                            score = scores.scores.overall_score
                    elif account.current_stage == "negotiation":
                        scores = repo.get_call_close_scores(call.call_id)
                        if scores:
                            score = scores.scores.overall_score

                    if score is not None and score < 2.5:
                        at_risk_count += 1

        # Format rep name
        rep_name = rep_email.split("@")[0] if "@" in rep_email else rep_email

        rep_data[rep_email] = {
            "name": rep_name,
            "email": rep_email,
            "segment": (rep.segment or "unknown").title(),
            "total_calls": len(rep_calls),
            "total_accounts": len(account_ids),
            "win_rate": win_rate,
            "discovery_avg": sum(discovery_scores) / len(discovery_scores) if discovery_scores else None,
            "trial_avg": sum(trial_scores) / len(trial_scores) if trial_scores else None,
            "negotiation_avg": sum(negotiation_scores) / len(negotiation_scores) if negotiation_scores else None,
            "discovery_count": len(discovery_scores),
            "trial_count": len(trial_scores),
            "negotiation_count": len(negotiation_scores),
            "active_deals": len(active_accounts),
            "at_risk_deals": at_risk_count,
            "closed_deals": len(closed_accounts),
            "won_deals": won_accounts,
        }

    return list(rep_data.values())


# ============================================================================
# Charts
# ============================================================================

def build_rep_comparison_chart(rep_data: List[Dict], metric: str = "discovery_avg") -> go.Figure:
    """Build bar chart comparing reps on a key metric."""
    # Filter out reps with no data for the metric
    if metric == "discovery_avg":
        valid_reps = [r for r in rep_data if r["discovery_avg"] is not None]
        metric_label = "Avg Discovery Score"
        metric_values = [r["discovery_avg"] for r in valid_reps]
    elif metric == "trial_avg":
        valid_reps = [r for r in rep_data if r["trial_avg"] is not None]
        metric_label = "Avg Trial Score"
        metric_values = [r["trial_avg"] for r in valid_reps]
    elif metric == "negotiation_avg":
        valid_reps = [r for r in rep_data if r["negotiation_avg"] is not None]
        metric_label = "Avg Negotiation Score"
        metric_values = [r["negotiation_avg"] for r in valid_reps]
    else:
        return None

    if not valid_reps:
        return None

    # Sort by metric
    sorted_reps = sorted(zip(valid_reps, metric_values), key=lambda x: x[1], reverse=True)
    valid_reps = [r[0] for r in sorted_reps]
    metric_values = [r[1] for r in sorted_reps]

    # Create colors based on score (color-blind friendly palette)
    colors = []
    for val in metric_values:
        if val >= 4.0:
            colors.append("#0d7fa6")  # Blue (high)
        elif val >= 2.5:
            colors.append("#7eb36a")  # Teal/green (medium)
        else:
            colors.append("#d4526e")  # Pink/magenta (low)

    fig = go.Figure(data=[go.Bar(
        x=[r["name"] for r in valid_reps],
        y=metric_values,
        marker=dict(color=colors),
        text=[f"{v:.1f}" for v in metric_values],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>' + metric_label + ': %{y}<extra></extra>'
    )])

    fig.update_layout(
        title=f"Rep Comparison - {metric_label}",
        xaxis_title="Sales Rep",
        yaxis_title=metric_label,
        height=400,
        showlegend=False
    )

    return fig


def build_dimension_heatmap(repo: Repository, rep_emails: List[str], stage: str,
                            date_from: Optional[datetime] = None, date_to: Optional[datetime] = None) -> go.Figure:
    """Build heatmap showing dimension scores for selected stage."""
    # Define dimensions by stage
    if stage == "discovery":
        dimensions = ["Metrics", "Economic Buyer", "Decision Criteria", "Decision Process",
                     "Paper Process", "Identify Pain", "Champion", "Competition"]
        dimension_keys = ["metrics", "economic_buyer", "decision_criteria", "decision_process",
                         "paper_process", "identify_pain", "champion", "competition"]
        title = "MEDDPICC Dimension Breakdown by Rep"
    elif stage == "trial":
        dimensions = ["Technical Validation", "Readiness & Progress", "Internal Adoption",
                     "Advocacy & Sentiment", "Landscape & Competition"]
        dimension_keys = ["technical_validation", "readiness_progress", "internal_adoption",
                         "advocacy_sentiment", "landscape_competition"]
        title = "TRIAL Dimension Breakdown by Rep"
    elif stage == "negotiation":
        dimensions = ["Commercial Alignment", "Legal & Compliance", "Organizational Consensus",
                     "Single-Threading Risk", "Execution Momentum"]
        dimension_keys = ["commercial_alignment", "legal_compliance", "organizational_consensus",
                         "single_threading_risk", "execution_momentum"]
        title = "CLOSE Dimension Breakdown by Rep"
    else:
        return None

    # Collect dimension scores for each rep
    rep_dimension_scores = {}

    for rep_email in rep_emails:
        rep_name = rep_email.split("@")[0] if "@" in rep_email else rep_email

        # Get all calls for this rep in this stage (with date filter)
        query_parts = ["SELECT * FROM calls WHERE sales_rep_email = ? AND primary_stage = ?"]
        params = [rep_email, stage]

        if date_from:
            query_parts.append("AND call_date >= ?")
            params.append(date_from)
        if date_to:
            query_parts.append("AND call_date <= ?")
            params.append(date_to)

        query = " ".join(query_parts)
        cursor = repo.conn.execute(query, params)
        call_rows = cursor.fetchall()

        if not call_rows:
            continue

        # Aggregate dimension scores
        dimension_scores = defaultdict(list)

        for call_row in call_rows:
            call = repo._row_to_call(call_row)

            if stage == "discovery":
                scores = repo.get_call_meddpicc_scores(call.call_id)
                if scores:
                    s = scores.scores
                    for key in dimension_keys:
                        dimension_scores[key].append(getattr(s, key))
            elif stage == "trial":
                scores = repo.get_call_trial_scores(call.call_id)
                if scores:
                    s = scores.scores
                    for key in dimension_keys:
                        dimension_scores[key].append(getattr(s, key))
            elif stage == "negotiation":
                scores = repo.get_call_close_scores(call.call_id)
                if scores:
                    s = scores.scores
                    for key in dimension_keys:
                        dimension_scores[key].append(getattr(s, key))

        # Calculate averages
        if dimension_scores:
            rep_dimension_scores[rep_name] = {
                key: sum(scores) / len(scores) if scores else 0
                for key, scores in dimension_scores.items()
            }

    if not rep_dimension_scores:
        return None

    # Sort reps by name
    rep_names = sorted(rep_dimension_scores.keys())

    # Build score matrix (dimensions x reps)
    score_matrix = []
    for dim_key in dimension_keys:
        row = [rep_dimension_scores[rep_name].get(dim_key, 0) for rep_name in rep_names]
        score_matrix.append(row)

    # Create custom hover text
    hover_text = []
    for dim_idx, dim_label in enumerate(dimensions):
        dim_hover = []
        for rep_idx, rep_name in enumerate(rep_names):
            score = score_matrix[dim_idx][rep_idx]
            if score > 0:
                dim_hover.append(f"<b>{rep_name}</b><br>{dim_label}: {score:.1f}")
            else:
                dim_hover.append(f"<b>{rep_name}</b><br>{dim_label}: N/A")
        hover_text.append(dim_hover)

    fig = go.Figure(data=go.Heatmap(
        z=score_matrix,
        x=rep_names,
        y=dimensions,
        colorscale="Viridis",  # Color-blind friendly: dark purple (low) to yellow (high)
        zmin=0,
        zmax=5,
        hovertext=hover_text,
        hovertemplate='%{hovertext}<extra></extra>',
        colorbar=dict(
            title="Score",
            tickvals=[0, 1, 2, 3, 4, 5],
            ticktext=["0", "1", "2", "3", "4", "5"]
        )
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Sales Rep",
        yaxis_title="Dimension",
        height=400,
        xaxis={'side': 'bottom'},
    )

    return fig


# ============================================================================
# Table Building
# ============================================================================

def build_reps_table(rep_data: List[Dict]) -> List[Dict]:
    """Build table data for reps."""
    table_data = []

    for i, rep in enumerate(rep_data, 1):
        row = {
            "#": i,
            "Rep": rep["name"],
            "Segment": rep["segment"],
            "Calls": rep["total_calls"],
            "Accounts": rep["total_accounts"],
            "Discovery Avg": f"{rep['discovery_avg']:.1f}" if rep['discovery_avg'] is not None else "N/A",
            "Trial Avg": f"{rep['trial_avg']:.1f}" if rep['trial_avg'] is not None else "N/A",
            "Negotiation Avg": f"{rep['negotiation_avg']:.1f}" if rep['negotiation_avg'] is not None else "N/A",
            "Active Deals": rep["active_deals"],
            "At Risk": rep["at_risk_deals"],
            "_email": rep["email"]
        }
        table_data.append(row)

    return table_data


# ============================================================================
# Rep Detail View
# ============================================================================

def show_rep_detail(rep_email: str, repo: Repository, date_from: Optional[datetime] = None,
                    date_to: Optional[datetime] = None):
    """Show detailed rep profile."""
    # Get rep info
    rep = repo.get_sales_rep(rep_email)
    if not rep:
        st.error("Rep not found")
        return

    rep_name = rep_email.split("@")[0] if "@" in rep_email else rep_email

    # Header
    st.markdown(f"## 👤 {rep_name}")
    st.markdown(f"**Email:** {rep_email}")
    st.markdown(f"**Segment:** {(rep.segment or 'unknown').title()}")

    # Add joining date and days on job
    if rep.joining_date:
        # Handle both date and datetime types
        if isinstance(rep.joining_date, str):
            joining_dt = datetime.fromisoformat(rep.joining_date)
        elif isinstance(rep.joining_date, datetime):
            joining_dt = rep.joining_date
        else:  # date object
            joining_dt = datetime.combine(rep.joining_date, datetime.min.time())

        days_on_job = (datetime.now() - joining_dt).days
        st.markdown(f"**Joined:** {joining_dt.strftime('%Y-%m-%d')} ({days_on_job} days on the job)")

    st.markdown("---")

    # Get all calls for this rep (with date filter)
    query_parts = ["SELECT * FROM calls WHERE sales_rep_email = ?"]
    params = [rep_email]

    if date_from:
        query_parts.append("AND call_date >= ?")
        params.append(date_from)
    if date_to:
        query_parts.append("AND call_date <= ?")
        params.append(date_to)

    query_parts.append("ORDER BY call_date DESC")
    query = " ".join(query_parts)

    cursor = repo.conn.execute(query, params)
    call_rows = cursor.fetchall()

    if not call_rows:
        st.info("No calls found for this rep in the selected date range.")
        return

    # Calculate dimension scores
    discovery_dimension_scores = defaultdict(list)
    trial_dimension_scores = defaultdict(list)
    negotiation_dimension_scores = defaultdict(list)

    discovery_calls = []
    trial_calls = []
    negotiation_calls = []

    for call_row in call_rows:
        call = repo._row_to_call(call_row)

        if call.primary_stage == "discovery":
            scores = repo.get_call_meddpicc_scores(call.call_id)
            if scores:
                s = scores.scores
                discovery_dimension_scores["Metrics"].append(s.metrics)
                discovery_dimension_scores["Economic Buyer"].append(s.economic_buyer)
                discovery_dimension_scores["Decision Criteria"].append(s.decision_criteria)
                discovery_dimension_scores["Decision Process"].append(s.decision_process)
                discovery_dimension_scores["Paper Process"].append(s.paper_process)
                discovery_dimension_scores["Identify Pain"].append(s.identify_pain)
                discovery_dimension_scores["Champion"].append(s.champion)
                discovery_dimension_scores["Competition"].append(s.competition)
                discovery_calls.append((call, s))

        elif call.primary_stage == "trial":
            scores = repo.get_call_trial_scores(call.call_id)
            if scores:
                s = scores.scores
                trial_dimension_scores["Technical Validation"].append(s.technical_validation)
                trial_dimension_scores["Readiness & Progress"].append(s.readiness_progress)
                trial_dimension_scores["Internal Adoption"].append(s.internal_adoption)
                trial_dimension_scores["Advocacy & Sentiment"].append(s.advocacy_sentiment)
                trial_dimension_scores["Landscape & Competition"].append(s.landscape_competition)
                trial_calls.append((call, s))

        elif call.primary_stage == "negotiation":
            scores = repo.get_call_close_scores(call.call_id)
            if scores:
                s = scores.scores
                negotiation_dimension_scores["Commercial Alignment"].append(s.commercial_alignment)
                negotiation_dimension_scores["Legal & Compliance"].append(s.legal_compliance)
                negotiation_dimension_scores["Organizational Consensus"].append(s.organizational_consensus)
                negotiation_dimension_scores["Single-Threading Risk"].append(s.single_threading_risk)
                negotiation_dimension_scores["Execution Momentum"].append(s.execution_momentum)
                negotiation_calls.append((call, s))

    # Performance Summary
    st.markdown("### 📊 Performance Summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Calls", len(call_rows))

    with col2:
        if discovery_calls:
            avg_discovery = sum(s.overall_score for _, s in discovery_calls) / len(discovery_calls)
            st.metric("🔍 Discovery Avg", f"{avg_discovery:.1f}")
        else:
            st.metric("🔍 Discovery Avg", "N/A")

    with col3:
        if trial_calls:
            avg_trial = sum(s.overall_score for _, s in trial_calls) / len(trial_calls)
            st.metric("🧪 Trial Avg", f"{avg_trial:.1f}")
        else:
            st.metric("🧪 Trial Avg", "N/A")

    with col4:
        if negotiation_calls:
            avg_negotiation = sum(s.overall_score for _, s in negotiation_calls) / len(negotiation_calls)
            st.metric("💼 Negotiation Avg", f"{avg_negotiation:.1f}")
        else:
            st.metric("💼 Negotiation Avg", "N/A")

    st.markdown("---")

    # Dimension Breakdown - Strengths & Weaknesses
    st.markdown("### 🎯 Dimension Analysis")

    # Show dimension breakdowns by stage
    if discovery_dimension_scores:
        st.markdown("#### 🔍 MEDDPICC (Discovery)")

        # Calculate averages
        dim_avgs = {dim: sum(scores) / len(scores) for dim, scores in discovery_dimension_scores.items()}

        # Sort by score
        sorted_dims = sorted(dim_avgs.items(), key=lambda x: x[1], reverse=True)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Strengths (≥4.0):**")
            strengths = [d for d in sorted_dims if d[1] >= 4.0]
            if strengths:
                for dim, score in strengths:
                    st.markdown(f"- 🟢 {dim}: {score:.1f}")
            else:
                st.markdown("*No dimensions ≥4.0*")

        with col2:
            st.markdown("**Needs Improvement (<3.0):**")
            weaknesses = [d for d in sorted_dims if d[1] < 3.0]
            if weaknesses:
                for dim, score in weaknesses:
                    st.markdown(f"- 🔴 {dim}: {score:.1f}")
            else:
                st.markdown("*All dimensions ≥3.0*")

        st.markdown("---")

    if trial_dimension_scores:
        st.markdown("#### 🧪 TRIAL Health")

        dim_avgs = {dim: sum(scores) / len(scores) for dim, scores in trial_dimension_scores.items()}
        sorted_dims = sorted(dim_avgs.items(), key=lambda x: x[1], reverse=True)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Strengths (≥4.0):**")
            strengths = [d for d in sorted_dims if d[1] >= 4.0]
            if strengths:
                for dim, score in strengths:
                    st.markdown(f"- 🟢 {dim}: {score:.1f}")
            else:
                st.markdown("*No dimensions ≥4.0*")

        with col2:
            st.markdown("**Needs Improvement (<3.0):**")
            weaknesses = [d for d in sorted_dims if d[1] < 3.0]
            if weaknesses:
                for dim, score in weaknesses:
                    st.markdown(f"- 🔴 {dim}: {score:.1f}")
            else:
                st.markdown("*All dimensions ≥3.0*")

        st.markdown("---")

    if negotiation_dimension_scores:
        st.markdown("#### 💼 CLOSE Health (Negotiation)")

        dim_avgs = {dim: sum(scores) / len(scores) for dim, scores in negotiation_dimension_scores.items()}
        sorted_dims = sorted(dim_avgs.items(), key=lambda x: x[1], reverse=True)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Strengths (≥4.0):**")
            strengths = [d for d in sorted_dims if d[1] >= 4.0]
            if strengths:
                for dim, score in strengths:
                    st.markdown(f"- 🟢 {dim}: {score:.1f}")
            else:
                st.markdown("*No dimensions ≥4.0*")

        with col2:
            st.markdown("**Needs Improvement (<3.0):**")
            weaknesses = [d for d in sorted_dims if d[1] < 3.0]
            if weaknesses:
                for dim, score in weaknesses:
                    st.markdown(f"- 🔴 {dim}: {score:.1f}")
            else:
                st.markdown("*All dimensions ≥3.0*")

        st.markdown("---")

    # Recent calls
    st.markdown("### 📞 Recent Calls")
    st.markdown(f"Showing last 10 calls")

    recent_calls_data = []
    for call_row in call_rows[:10]:
        call = repo._row_to_call(call_row)

        # Get account
        account = repo.get_account(call.account_id)
        account_domain = account.domain if account else "Unknown"

        # Get score
        score = "N/A"
        if call.primary_stage == "discovery":
            scores = repo.get_call_meddpicc_scores(call.call_id)
            if scores:
                score = f"{scores.scores.overall_score:.1f}"
        elif call.primary_stage == "trial":
            scores = repo.get_call_trial_scores(call.call_id)
            if scores:
                score = f"{scores.scores.overall_score:.1f}"
        elif call.primary_stage == "negotiation":
            scores = repo.get_call_close_scores(call.call_id)
            if scores:
                score = f"{scores.scores.overall_score:.1f}"

        recent_calls_data.append({
            "Date": format_date(call.call_date),
            "Account": account_domain,
            "Stage": call.primary_stage.title(),
            "Score": score,
            "Title": call.call_title[:60] + "..." if len(call.call_title) > 60 else call.call_title,
            "Gong": format_gong_link(call.call_id)
        })

    if recent_calls_data:
        df = pd.DataFrame(recent_calls_data)
        st.dataframe(
            df,
            column_config={
                "Gong": st.column_config.LinkColumn("Gong", display_text="🔗 View"),
            },
            hide_index=True,
            use_container_width=True
        )


# ============================================================================
# Main App
# ============================================================================

def main():
    """Main reps dashboard."""
    st.title("👥 Reps Dashboard")
    st.markdown("Compare sales rep performance and identify coaching opportunities")

    # Load database connection
    config = Config()
    db = Database(config.SQLITE_DB_PATH)
    db.connect()
    repo = Repository(db.conn)

    try:
        # Load segments from database for filter
        sales_reps = repo.list_sales_reps()
        segments = sorted(set(rep.segment for rep in sales_reps if rep.segment))

        # Sidebar filters
        st.sidebar.header("Filters")

        # Date range
        date_options = {
            "Last 7 days": 7,
            "Last 30 days": 30,
            "Last 90 days": 90,
            "All time": None
        }

        date_selection = st.sidebar.selectbox(
            "Date Range",
            options=list(date_options.keys()),
            index=2  # Default to last 90 days
        )

        days = date_options[date_selection]
        date_from = datetime.now() - timedelta(days=days) if days else None
        date_to = None

        # Segment filter
        segment_options = ["All"] + [seg.title() for seg in segments]
        segment_selection = st.sidebar.selectbox(
            "Segment",
            options=segment_options,
            index=0
        )

        # Stage filter
        stage_selection = st.sidebar.selectbox(
            "Stage",
            options=["All", "Discovery", "Trial", "Negotiation", "Closed"],
            index=0
        )

        st.sidebar.markdown("---")

        # Glossary section
        with st.sidebar.expander("📚 Scoring Glossary", expanded=False):
            st.markdown("### MEDDPICC (Discovery)")
            st.markdown("**Goal:** Qualify the opportunity")
            st.markdown("""
**Dimensions:**
- **M**etrics: Quantifiable success metrics
- **E**conomic Buyer: Budget holder identified
- **D**ecision Criteria: Evaluation criteria documented
- **D**ecision Process: Process mapped with timeline
- **P**aper Process: Procurement/legal process
- **I**dentify Pain: Business pain articulated
- **C**hampion: Internal advocate identified
- **C**ompetition: Competitive landscape understood

**Scoring:**
- **5**: Fully understood with specifics
- **2**: Partially understood
- **0**: Not understood
            """)

            st.markdown("---")
            st.markdown("### TRIAL Health")
            st.markdown("**Goal:** Assess trial health and likelihood to advance")
            st.markdown("""
**Dimensions:**
- **T**echnical Validation: Product working successfully
- **R**eadiness & Progress: On schedule with compelling results
- **I**nternal Adoption: High user engagement
- **A**dvocacy & Sentiment: Champion confident, stakeholders aligned
- **L**andscape & Competition: Clear leader or sole vendor

**Scoring:**
- **5**: Healthy, no concerns
- **2**: Some concerns, addressable
- **0**: Critical issues
            """)

            st.markdown("---")
            st.markdown("### CLOSE Health (Negotiation)")
            st.markdown("**Goal:** Assess deal health and likelihood to close")
            st.markdown("""
**Dimensions:**
- **C**ommercial Alignment: Pricing agreed, ROI compelling
- **L**egal & Compliance: Requirements met
- **O**rganizational Consensus: Stakeholders aligned
- **S**ingle-Threading Risk: Multi-threaded relationships
- **E**xecution Momentum: Active progress toward close

**Scoring:**
- **5**: Healthy, on track to close
- **2**: Some concerns, needs attention
- **0**: Critical blockers
            """)

        st.markdown("---")

        # Load filtered data
        with st.spinner("Loading rep performance data..."):
            rep_data = load_rep_performance(
                repo,
                segment=segment_selection.lower() if segment_selection != "All" else None,
                stage=stage_selection if stage_selection != "All" else None,
                date_from=date_from,
                date_to=date_to
            )

        if not rep_data:
            st.warning("No rep data found with the selected filters.")
            return

        # Summary metrics
        st.markdown("---")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("👥 Active Reps", len(rep_data))

        with col2:
            # Calculate total calls across all reps
            total_calls = sum(r["total_calls"] for r in rep_data)
            st.metric("📞 Total Calls", total_calls)

        with col3:
            # Calculate total accounts across all reps
            total_accounts = sum(r["total_accounts"] for r in rep_data)
            st.metric("🏢 Total Accounts", total_accounts)

        with col4:
            # Calculate team average score (across all stages)
            all_scores = []
            for r in rep_data:
                if r["discovery_avg"]:
                    all_scores.append(r["discovery_avg"])
                if r["trial_avg"]:
                    all_scores.append(r["trial_avg"])
                if r["negotiation_avg"]:
                    all_scores.append(r["negotiation_avg"])

            if all_scores:
                team_avg = sum(all_scores) / len(all_scores)
                st.metric("📈 Team Avg Score", f"{team_avg:.1f}")
            else:
                st.metric("📈 Team Avg Score", "N/A")

        st.markdown("---")

        # Comparison chart
        chart_metric = st.selectbox(
            "Compare reps by:",
            options=["discovery_avg", "trial_avg", "negotiation_avg"],
            format_func=lambda x: {
                "discovery_avg": "Discovery Avg Score",
                "trial_avg": "Trial Avg Score",
                "negotiation_avg": "Negotiation Avg Score"
            }[x],
            index=0
        )

        comparison_chart = build_rep_comparison_chart(rep_data, chart_metric)
        if comparison_chart:
            st.plotly_chart(comparison_chart, use_container_width=True)
        else:
            st.info("No data available for selected metric.")

        # Heatmap showing dimension breakdown for selected stage
        rep_emails = [r["email"] for r in rep_data]

        # Map chart metric to stage
        metric_to_stage = {
            "discovery_avg": "discovery",
            "trial_avg": "trial",
            "negotiation_avg": "negotiation"
        }
        selected_stage = metric_to_stage.get(chart_metric)

        if selected_stage:
            heatmap = build_dimension_heatmap(repo, rep_emails, selected_stage, date_from, date_to)
            if heatmap:
                st.plotly_chart(heatmap, use_container_width=True)
            else:
                st.info("No dimension data available for heatmap.")

        st.markdown("---")

        # Reps table
        st.markdown("### 📊 Rep Performance")
        table_data = build_reps_table(rep_data)

        if not table_data:
            st.info("No rep data available.")
            return

        # Display table
        df = pd.DataFrame(table_data)
        display_columns = [col for col in df.columns if not col.startswith('_')]
        display_df = df[display_columns]

        st.markdown("**Click on a row to view rep details**")

        event = st.dataframe(
            display_df,
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        st.markdown(f"**Showing {len(table_data)} rep(s)**")

        # Handle row selection with session state
        if event.selection.rows:
            selected_row_idx = event.selection.rows[0]
            selected_rep_email = table_data[selected_row_idx]['_email']
            st.session_state['selected_rep_email'] = selected_rep_email

        # Show selected rep details from session state
        if 'selected_rep_email' in st.session_state:
            st.markdown("---")
            show_rep_detail(st.session_state['selected_rep_email'], repo, date_from, date_to)

    finally:
        db.close()


if __name__ == "__main__":
    main()
