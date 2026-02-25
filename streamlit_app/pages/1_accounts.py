"""Multi-Stage Account Dashboard - Track accounts across discovery, trial, negotiation, and closed stages."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core import Config
from src.data import Database, Repository

# Page config
st.set_page_config(
    page_title="Accounts - Introspect",
    page_icon="🏢",
    layout="wide"
)


# ============================================================================
# Styling & Constants
# ============================================================================

STAGE_EMOJIS = {
    "discovery": "🔍",
    "trial": "🧪",
    "negotiation": "💼",
    "closed": "✅"
}

STAGE_COLORS = {
    "discovery": "#3498db",    # Blue
    "trial": "#f39c12",        # Orange
    "negotiation": "#9b59b6",  # Purple
    "closed": "#2ecc71"        # Green
}

HEALTH_EMOJIS = {
    "healthy": "🟢",
    "at_risk": "🟡",
    "critical": "🔴"
}

OUTCOME_EMOJIS = {
    "won": "✅",
    "lost": "❌"
}

# Personal email domains to exclude (not business accounts)
PERSONAL_EMAIL_DOMAINS = {
    "gmail.com",
    "hotmail.com",
    "yahoo.com",
    "outlook.com",
    "icloud.com",
    "me.com",
    "aol.com",
    "live.com",
    "msn.com",
    "protonmail.com",
    "proton.me",
    "mail.com",
    "ymail.com",
    "googlemail.com"
}


def get_score_color(score: float) -> str:
    """Get color based on score (0-5 scale)."""
    if score >= 4.0:
        return "#2ecc71"  # Green
    elif score >= 2.5:
        return "#f39c12"  # Orange
    else:
        return "#e74c3c"  # Red


def get_score_emoji(score: float) -> str:
    """Get emoji based on score."""
    if score >= 4.0:
        return "🟢"
    elif score >= 2.5:
        return "🟡"
    else:
        return "🔴"


def format_date(dt: datetime) -> str:
    """Format datetime for display."""
    if dt is None:
        return "N/A"
    return dt.strftime("%b %d, %Y")


def format_gong_link(call_id: str) -> str:
    """Format Gong call link."""
    return f"https://us-35231.app.gong.io/call?id={call_id}"


# ============================================================================
# Data Loading
# ============================================================================

def load_data(stage: Optional[str] = None, segment: Optional[str] = None):
    """Load accounts from database with filtering."""
    config = Config()
    db = Database(config.SQLITE_DB_PATH)
    db.connect()
    repo = Repository(db.conn)

    try:
        # Get all accounts
        accounts = repo.list_accounts()

        # Filter out personal email domains
        accounts = [a for a in accounts if a.domain not in PERSONAL_EMAIL_DOMAINS]

        # Filter by stage
        if stage and stage != "All":
            accounts = [a for a in accounts if a.current_stage == stage.lower()]

        # Filter by segment
        if segment and segment != "All":
            accounts = [a for a in accounts if a.primary_segment == segment.lower()]

        # Get sales reps for segment list
        sales_reps = repo.list_sales_reps()
        segments = sorted(set(rep.segment for rep in sales_reps if rep.segment))

        return accounts, segments
    finally:
        db.close()


def get_all_calls_for_account(repo: Repository, account_id: int) -> Dict[str, List]:
    """Get ALL calls for an account, grouped by stage."""
    query = """
        SELECT * FROM calls
        WHERE account_id = ?
        ORDER BY call_date DESC
    """
    cursor = repo.conn.execute(query, (account_id,))
    rows = cursor.fetchall()

    # Group by stage
    calls_by_stage = {
        "discovery": [],
        "trial": [],
        "negotiation": [],
        "closed": []
    }

    for row in rows:
        call = repo._row_to_call(row)
        stage = call.primary_stage

        # Load stage-specific scores
        if stage == "discovery":
            scores = repo.get_call_meddpicc_scores(call.call_id)
            if scores:
                call.meddpicc_scores = scores.scores
        elif stage == "trial":
            scores = repo.get_call_trial_scores(call.call_id)
            if scores:
                call.trial_scores = scores.scores
        elif stage == "negotiation":
            scores = repo.get_call_close_scores(call.call_id)
            if scores:
                call.close_scores = scores.scores
        elif stage == "closed":
            analysis = repo.get_call_win_loss_analysis(call.call_id)
            if analysis:
                call.winloss_analysis = analysis.analysis

        if stage in calls_by_stage:
            calls_by_stage[stage].append(call)

    return calls_by_stage


def get_calls_for_account_stage(repo: Repository, account_id: int, stage: str) -> List:
    """Get calls for an account in a specific stage."""
    # Get all calls for account
    query = """
        SELECT * FROM calls
        WHERE account_id = ? AND primary_stage = ?
        ORDER BY call_date DESC
    """
    cursor = repo.conn.execute(query, (account_id, stage))
    rows = cursor.fetchall()

    calls = []
    for row in rows:
        call = repo._row_to_call(row)

        # Load stage-specific scores
        if stage == "discovery":
            scores = repo.get_call_meddpicc_scores(call.call_id)
            if scores:
                call.meddpicc_scores = scores.scores
        elif stage == "trial":
            scores = repo.get_call_trial_scores(call.call_id)
            if scores:
                call.trial_scores = scores.scores
        elif stage == "negotiation":
            scores = repo.get_call_close_scores(call.call_id)
            if scores:
                call.close_scores = scores.scores
        elif stage == "closed":
            analysis = repo.get_call_win_loss_analysis(call.call_id)
            if analysis:
                call.winloss_analysis = analysis.analysis

        calls.append(call)

    return calls


# ============================================================================
# Charts
# ============================================================================

def build_portfolio_bubble_chart(accounts: List, repo: Repository) -> go.Figure:
    """Build portfolio bubble chart showing all accounts."""
    data_points = []

    for account in accounts:
        if not account.last_call_date:
            continue

        # Get most recent call for this account's current stage
        stage = account.current_stage or "unknown"
        if stage == "unknown":
            continue

        calls = get_calls_for_account_stage(repo, account.id, stage)
        if not calls:
            continue

        most_recent_call = calls[0]

        # Determine score and color
        if stage == "discovery":
            if hasattr(most_recent_call, 'meddpicc_scores'):
                score = most_recent_call.meddpicc_scores.overall_score
            else:
                score = 0
            color = STAGE_COLORS["discovery"]
            stage_label = "Discovery"

        elif stage == "trial":
            if hasattr(most_recent_call, 'trial_scores'):
                score = most_recent_call.trial_scores.overall_score
            else:
                score = 0
            color = STAGE_COLORS["trial"]
            stage_label = "Trial"

        elif stage == "negotiation":
            if hasattr(most_recent_call, 'close_scores'):
                score = most_recent_call.close_scores.overall_score
            else:
                score = 0
            color = STAGE_COLORS["negotiation"]
            stage_label = "Negotiation"

        elif stage == "closed":
            # Fixed size for closed, but different colors for won/lost
            score = 3.0  # Fixed size
            if hasattr(most_recent_call, 'winloss_analysis'):
                outcome = most_recent_call.winloss_analysis.outcome
                if outcome == "won":
                    color = "#2ecc71"  # Bright green
                    stage_label = "Closed Won"
                else:
                    color = "#e74c3c"  # Red
                    stage_label = "Closed Lost"
            else:
                color = STAGE_COLORS["closed"]
                stage_label = "Closed"
        else:
            continue

        data_points.append({
            "account": account.domain,
            "last_call_date": account.last_call_date,
            "total_calls": account.total_calls,
            "score": score,
            "color": color,
            "stage": stage_label,
            "days_in_stage": account.days_in_current_stage() or 0
        })

    if not data_points:
        return None

    # Create scatter plot
    fig = go.Figure()

    # Group by stage for legend
    stages = {}
    for point in data_points:
        stage = point["stage"]
        if stage not in stages:
            stages[stage] = []
        stages[stage].append(point)

    # Add trace for each stage
    for stage, points in stages.items():
        fig.add_trace(go.Scatter(
            x=[p["last_call_date"] for p in points],
            y=[p["total_calls"] for p in points],
            mode='markers',
            name=stage,
            marker=dict(
                size=[p["score"] * 10 + 10 for p in points],  # Scale size
                color=points[0]["color"],
                opacity=0.7,
                line=dict(color='white', width=1)
            ),
            text=[p["account"] for p in points],
            hovertemplate=(
                '<b>%{text}</b><br>'
                'Last Call: %{x|%b %d, %Y}<br>'
                'Total Calls: %{y}<br>'
                'Days in Stage: ' + '<br>'.join([str(p["days_in_stage"]) for p in points]) + '<br>'
                '<extra></extra>'
            )
        ))

    fig.update_layout(
        title="Portfolio Overview - Account Activity & Health",
        xaxis_title="Last Call Date",
        yaxis_title="Total Calls",
        height=500,
        hovermode='closest',
        showlegend=True
    )

    return fig


def build_stage_distribution_chart(accounts: List) -> go.Figure:
    """Build pie chart showing account distribution by stage."""
    stage_counts = {}
    for account in accounts:
        stage = account.current_stage or "unknown"
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    labels = [stage.title() for stage in stage_counts.keys()]
    values = list(stage_counts.values())
    colors = [STAGE_COLORS.get(stage, "#95a5a6") for stage in stage_counts.keys()]

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors),
        hole=0.3,
        textinfo='label+value+percent',
        hovertemplate='<b>%{label}</b><br>Accounts: %{value}<br>%{percent}<extra></extra>'
    )])

    fig.update_layout(
        title="Account Distribution by Stage",
        height=400,
        showlegend=True
    )

    return fig


def build_dimension_trend_chart(calls: List, stage: str) -> go.Figure:
    """Build grouped vertical bar chart showing dimension scores for each call."""
    if not calls:
        return None

    # Sort calls by date
    sorted_calls = sorted(calls, key=lambda c: c.call_date)

    # Define dimensions by stage
    if stage == "discovery":
        dimensions = ["metrics", "economic_buyer", "decision_criteria", "decision_process",
                     "paper_process", "identify_pain", "champion", "competition"]
        full_labels = ["Metrics", "Econ Buyer", "Decision Criteria", "Decision Process",
                      "Paper Process", "Identify Pain", "Champion", "Competition"]
        score_attr = "meddpicc_scores"
        title = "MEDDPICC Dimension Scores"
    elif stage == "trial":
        dimensions = ["technical_validation", "readiness_progress", "internal_adoption",
                     "advocacy_sentiment", "landscape_competition"]
        full_labels = ["Tech Validation", "Readiness", "Adoption",
                      "Advocacy", "Competition"]
        score_attr = "trial_scores"
        title = "TRIAL Dimension Scores"
    elif stage == "negotiation":
        dimensions = ["commercial_alignment", "legal_compliance", "organizational_consensus",
                     "single_threading_risk", "execution_momentum"]
        full_labels = ["Commercial", "Legal", "Consensus",
                      "Threading Risk", "Momentum"]
        score_attr = "close_scores"
        title = "CLOSE Dimension Scores"
    else:
        return None

    # Color-blind friendly palette (Viridis-inspired)
    colors = [
        '#440154',  # Dark purple
        '#31688e',  # Blue
        '#35b779',  # Green
        '#fde724',  # Yellow
        '#b5367a',  # Pink
        '#1f9e89',  # Teal
        '#95d840',  # Light green
        '#dce319',  # Yellow-green
    ]

    fig = go.Figure()

    # Add a bar trace for each dimension
    total_traces = 0
    for i, (dim, label) in enumerate(zip(dimensions, full_labels)):
        date_strs = []
        scores = []

        for call in sorted_calls:
            if hasattr(call, score_attr):
                score_obj = getattr(call, score_attr)
                if score_obj and hasattr(score_obj, dim):
                    # Format date as string for categorical x-axis (prevents overlap)
                    date_str = call.call_date.strftime('%b %d, %Y')
                    date_strs.append(date_str)
                    scores.append(getattr(score_obj, dim))

        if date_strs:
            total_traces += 1
            fig.add_trace(go.Bar(
                x=date_strs,
                y=scores,
                name=label,
                marker=dict(
                    color=colors[i % len(colors)],
                    line=dict(color='white', width=0.5)
                ),
                text=[f"{s:.1f}" for s in scores],
                textposition='inside',
                textfont=dict(color='white', size=10, family='Arial'),
                hovertemplate=f'<b>{label}</b><br>Date: %{{x}}<br>Score: %{{y:.1f}}/5.0<extra></extra>'
            ))

    fig.update_layout(
        title=title,
        xaxis_title="Call Date",
        yaxis_title="Score (0-5)",
        yaxis_range=[0, 5.5],
        barmode='group',  # Group bars side by side
        bargap=0.15,  # Gap between groups
        bargroupgap=0.05,  # Gap within groups
        height=400,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    return fig


def build_meddpicc_chart(scores) -> go.Figure:
    """Build MEDDPICC bar chart."""
    dimensions = ["metrics", "economic_buyer", "decision_criteria", "decision_process",
                  "paper_process", "identify_pain", "champion", "competition"]
    labels = ["M", "E", "DD", "DP", "P", "I", "C", "C"]
    values = [getattr(scores, dim) for dim in dimensions]
    colors = [get_score_color(v) for v in values]

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker=dict(color=colors),
        text=values,
        textposition='inside',
        hovertemplate='<b>%{x}</b><br>Score: %{y}/5<extra></extra>'
    ))

    fig.update_layout(
        title="MEDDPICC Coverage",
        xaxis_title="Dimension",
        yaxis_title="Score",
        yaxis_range=[0, 5],
        height=300,
        showlegend=False
    )

    return fig


def build_trial_chart(scores) -> go.Figure:
    """Build TRIAL bar chart."""
    dimensions = ["technical_validation", "readiness_progress", "internal_adoption",
                  "advocacy_sentiment", "landscape_competition"]
    labels = ["T", "R", "I", "A", "L"]
    values = [getattr(scores, dim) for dim in dimensions]
    colors = [get_score_color(v) for v in values]

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker=dict(color=colors),
        text=values,
        textposition='inside',
        hovertemplate='<b>%{x}</b><br>Score: %{y}/5<extra></extra>'
    ))

    fig.update_layout(
        title="TRIAL Health Dimensions",
        xaxis_title="Dimension",
        yaxis_title="Score",
        yaxis_range=[0, 5],
        height=300,
        showlegend=False
    )

    return fig


def build_close_chart(scores) -> go.Figure:
    """Build CLOSE bar chart."""
    dimensions = ["commercial_alignment", "legal_compliance", "organizational_consensus",
                  "single_threading_risk", "execution_momentum"]
    labels = ["C", "L", "O", "S", "E"]
    values = [getattr(scores, dim) for dim in dimensions]
    colors = [get_score_color(v) for v in values]

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker=dict(color=colors),
        text=values,
        textposition='inside',
        hovertemplate='<b>%{x}</b><br>Score: %{y}/5<extra></extra>'
    ))

    fig.update_layout(
        title="CLOSE Health Dimensions",
        xaxis_title="Dimension",
        yaxis_title="Score",
        yaxis_range=[0, 5],
        height=300,
        showlegend=False
    )

    return fig


# ============================================================================
# Stage Health Bubble Charts
# ============================================================================

def get_stage_bubble_data(repo: Repository, segment: str, stage: str) -> List[Dict]:
    """Get bubble chart data for a specific stage."""

    # Get all accounts in this stage
    accounts = repo.list_accounts(stage=stage)

    # Filter out personal email domains
    accounts = [a for a in accounts if a.domain not in PERSONAL_EMAIL_DOMAINS]

    # Filter by segment if specified
    if segment and segment != "All":
        accounts = [a for a in accounts if a.primary_segment == segment.lower()]

    data_points = []

    for account in accounts:
        # Calculate days in current stage
        days_in_stage = account.days_in_current_stage() or 0

        # Get calls in current stage
        calls_in_stage = get_calls_for_account_stage(repo, account.id, stage)
        num_calls_in_stage = len(calls_in_stage)

        # Total calls across all stages
        total_calls = account.total_calls or 0

        # Get health score based on stage
        health_score = None
        if calls_in_stage:
            most_recent_call = calls_in_stage[0]  # Already sorted by date DESC

            if stage == "discovery" and hasattr(most_recent_call, 'meddpicc_scores'):
                health_score = most_recent_call.meddpicc_scores.overall_score
            elif stage == "trial" and hasattr(most_recent_call, 'trial_scores'):
                health_score = most_recent_call.trial_scores.overall_score
            elif stage == "negotiation" and hasattr(most_recent_call, 'close_scores'):
                health_score = most_recent_call.close_scores.overall_score

        # Extract rep name from email
        rep_name = account.primary_sales_rep or "Unknown"
        if "@" in rep_name:
            rep_name = rep_name.split("@")[0]

        data_points.append({
            'account_id': account.id,
            'domain': account.domain,
            'days_in_stage': days_in_stage,
            'calls_in_stage': num_calls_in_stage,
            'total_calls': total_calls,
            'health_score': health_score,
            'rep_name': rep_name,
            'stage': stage
        })

    return data_points


def create_bubble_scatter_chart(data_points: List[Dict], stage: str, stage_emoji: str) -> go.Figure:
    """Create bubble scatter plot for stage health visualization."""

    if not data_points:
        # Empty chart
        fig = go.Figure()
        fig.update_layout(
            title=f"{stage_emoji} {stage.title()} (0 accounts)",
            annotations=[dict(
                text="No accounts in this stage",
                showarrow=False,
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                font=dict(size=16, color="#95a5a6")
            )],
            height=350
        )
        return fig

    # Separate by health score for coloring (simplified to 3 categories)
    green = []    # score >= 4
    yellow = []   # score 2-4
    red = []      # score < 2

    for dp in data_points:
        score = dp['health_score']
        if score is None:
            # Skip accounts with no score
            continue
        elif score >= 4.0:
            green.append(dp)
        elif score >= 2.0:
            yellow.append(dp)
        else:
            red.append(dp)

    # Calculate bubble sizes
    all_scored = green + yellow + red
    if not all_scored:
        # No scored accounts
        fig = go.Figure()
        fig.update_layout(
            title=f"{stage_emoji} {stage.title()} ({len(data_points)} accounts)",
            annotations=[dict(
                text="No evaluated accounts in this stage",
                showarrow=False,
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                font=dict(size=14, color="#95a5a6")
            )],
            height=350
        )
        return fig

    max_total_calls = max([dp['total_calls'] for dp in all_scored], default=1)

    def calc_bubble_size(total_calls):
        return 10 + (total_calls / max_total_calls) * 30

    fig = go.Figure()

    # Add traces for each health category (simplified)
    categories = [
        (red, "Red (< 2)", "#e74c3c"),
        (yellow, "Yellow (2-4)", "#f39c12"),
        (green, "Green (≥ 4)", "#2ecc71"),
    ]

    for data, name, color in categories:
        if not data:
            continue

        fig.add_trace(go.Scatter(
            x=[dp['calls_in_stage'] for dp in data],  # SWAPPED: calls on x-axis
            y=[dp['days_in_stage'] for dp in data],   # SWAPPED: days on y-axis
            mode='markers',
            name=name,
            marker=dict(
                size=[calc_bubble_size(dp['total_calls']) for dp in data],
                color=color,
                opacity=0.7,
                line=dict(width=1, color='white')
            ),
            text=[
                f"<b>{dp['domain']}</b><br>" +
                f"Calls: {dp['calls_in_stage']} | Days: {dp['days_in_stage']}<br>" +
                f"Score: {dp['health_score']:.1f}/5.0<br>" +
                f"Total Calls (all stages): {dp['total_calls']}<br>" +
                f"Rep: {dp['rep_name']}"
                for dp in data
            ],
            hovertemplate='%{text}<extra></extra>',
            customdata=[dp['domain'] for dp in data]  # Store domain in customdata
        ))

    # Update layout with swapped axes
    fig.update_layout(
        title=dict(
            text=f"{stage_emoji} {stage.title()} ({len(all_scored)} accounts)",
            font=dict(size=18, weight=600)
        ),
        xaxis=dict(
            title="Calls in Stage",
            gridcolor='#f1f5f9',
            showline=True,
            linewidth=1,
            linecolor='#e2e8f0',
            rangemode='tozero',
            showticklabels=True,
            tickmode='auto',
            nticks=10
        ),
        yaxis=dict(
            title="Days in Stage",
            gridcolor='#f1f5f9',
            showline=True,
            linewidth=1,
            linecolor='#e2e8f0',
            rangemode='tozero',
            showticklabels=True,
            tickmode='auto',
            nticks=10
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=500,
        showlegend=False,  # Remove legend
        margin=dict(l=60, r=30, t=60, b=50)
    )

    return fig


# ============================================================================
# Table Building
# ============================================================================

def build_table_data(accounts: List, stage: str, repo: Repository) -> List[Dict]:
    """Build table data adapted to the selected stage."""
    table_data = []

    for i, account in enumerate(accounts, 1):
        # Get calls for this account's current stage
        account_stage = account.current_stage or "unknown"
        if stage == "All":
            calls = get_calls_for_account_stage(repo, account.id, account_stage)
        else:
            calls = get_calls_for_account_stage(repo, account.id, stage.lower())

        if not calls:
            continue  # Skip accounts with no calls in selected stage

        # Get most recent call
        most_recent_call = calls[0]  # Already sorted by date DESC

        # Build row based on stage
        stage_emoji = STAGE_EMOJIS.get(account_stage, "📊")

        # Format sales rep email (show just the username part)
        sales_rep = account.primary_sales_rep or "unknown"
        if "@" in sales_rep:
            sales_rep = sales_rep.split("@")[0]

        gong_link = format_gong_link(most_recent_call.call_id)

        row = {
            "Account": account.domain,
            "Stage": f"{stage_emoji} {account_stage.title()}",
            "Segment": (account.primary_segment or "unknown").title(),
            "Sales Rep": sales_rep,
            "# Calls": len(calls),
            "Days in Stage": account.days_in_current_stage() or 0,
            "Last Call": format_date(account.last_call_date),
            "Call Title": most_recent_call.call_title,
            "gong_link": gong_link,
            "_account_id": account.id,
            "_stage": account_stage
        }

        # Add stage-specific columns (Score and Key Gap for discovery)
        if account_stage == "discovery":
            if hasattr(most_recent_call, 'meddpicc_scores'):
                score = most_recent_call.meddpicc_scores.overall_score
                row["Score"] = f"{score:.1f}"

                # Find weakest dimension
                dimensions = ["metrics", "economic_buyer", "decision_criteria", "decision_process",
                             "paper_process", "identify_pain", "champion", "competition"]
                dim_scores = {d: getattr(most_recent_call.meddpicc_scores, d) for d in dimensions}
                weakest = min(dim_scores.items(), key=lambda x: x[1])
                row["Key Gap"] = f"{weakest[0].replace('_', ' ').title()}: {weakest[1]}"

        elif account_stage == "trial":
            if hasattr(most_recent_call, 'trial_scores'):
                score = most_recent_call.trial_scores.overall_score
                row["Score"] = f"{score:.1f}"
                row["Primary Concern"] = (most_recent_call.trial_scores.primary_concern_category or "none").title()

        elif account_stage == "negotiation":
            if hasattr(most_recent_call, 'close_scores'):
                score = most_recent_call.close_scores.overall_score
                row["Score"] = f"{score:.1f}"
                row["Primary Concern"] = (most_recent_call.close_scores.primary_concern_category or "none").title()

        elif account_stage == "closed":
            # Keep only basic info for closed deals
            pass

        table_data.append(row)

    return table_data


# ============================================================================
# Detail View
# ============================================================================

def show_account_detail(account, repo: Repository):
    """Show detailed account view with full journey across all stages."""
    # Get ALL calls for this account, grouped by stage
    calls_by_stage = get_all_calls_for_account(repo, account.id)

    # Header with account name
    st.markdown(f"""
        <h3><i class="fas fa-building" style="color: #3498db;"></i> {account.domain}</h3>
    """, unsafe_allow_html=True)
    st.markdown("")

    # Two-column layout with visual panes (30/70 split)
    col1, col2 = st.columns([3, 7])

    with col1:
        with st.container(border=True):
            st.markdown('<p style="font-weight: bold;"><i class="fas fa-clipboard-list" style="color: #3498db;"></i> Account Information</p>', unsafe_allow_html=True)
            st.markdown(f"**Current Stage:** {(account.current_stage or 'unknown').title()}")
            st.markdown(f"**Days in Stage:** {account.days_in_current_stage() or 0} days")
            st.markdown(f"**Primary Sales Rep:** {account.primary_sales_rep or 'Unknown'}")
            st.markdown(f"**Segment:** {(account.primary_segment or 'unknown').title()}")
            st.markdown(f"**Total Calls:** {account.total_calls}")

    with col2:
        with st.container(border=True):
            st.markdown('<p style="font-weight: bold;"><i class="fas fa-users" style="color: #3498db;"></i> Customer Contacts</p>', unsafe_allow_html=True)

            # Get all call IDs for this account
            all_calls = []
            for stage_calls in calls_by_stage.values():
                all_calls.extend(stage_calls)

            if all_calls:
                # Collect unique external participants across all calls
                external_participants = {}
                for call in all_calls:
                    participants = repo.get_call_participants(call.call_id)
                    for speaker_id, participant in participants.items():
                        if participant.get('affiliation') == 'External':
                            email = participant.get('email_address')
                            if email and email not in external_participants:
                                external_participants[email] = participant

                if external_participants:
                    # Create DataFrame for compact table display
                    contacts_data = []
                    for email, p in external_participants.items():
                        contacts_data.append({
                            'Name': p.get('name', 'Unknown'),
                            'Title': p.get('title', ''),
                            'Email': email
                        })

                    contacts_df = pd.DataFrame(contacts_data)
                    st.dataframe(
                        contacts_df,
                        hide_index=True,
                        height=min(len(contacts_data) * 35 + 38, 300),  # Auto height, max 300px
                        width='stretch'
                    )
                else:
                    st.info("No participant data available")
            else:
                st.info("No calls yet")

    st.markdown("---")

    # Determine stage order (most recent first)
    stage_order = []
    stage_last_dates = {}

    for stage_name, calls in calls_by_stage.items():
        if calls:
            stage_last_dates[stage_name] = max(c.call_date for c in calls)

    # Sort stages by most recent activity
    for stage_name in sorted(stage_last_dates.keys(), key=lambda s: stage_last_dates[s], reverse=True):
        stage_order.append(stage_name)

    # Show each stage
    for stage_name in stage_order:
        calls = calls_by_stage[stage_name]
        if not calls:
            continue

        # Map stages to Font Awesome icons and colors
        stage_icons = {
            "discovery": ("fa-search", "#3498db"),
            "trial": ("fa-flask", "#9b59b6"),
            "negotiation": ("fa-briefcase", "#e67e22"),
            "closed": ("fa-check-circle", "#2ecc71")
        }
        icon_class, icon_color = stage_icons.get(stage_name, ("fa-chart-bar", "#95a5a6"))

        # Stage header
        st.markdown(f'<h2><i class="fas {icon_class}" style="color: {icon_color};"></i> {stage_name.upper()} STAGE</h2>', unsafe_allow_html=True)
        st.markdown(f"**Calls in this stage:** {len(calls)}")

        # Dimension trend chart (except for closed)
        if stage_name != "closed":
            trend_chart = build_dimension_trend_chart(calls, stage_name)
            if trend_chart:
                st.plotly_chart(trend_chart, width='stretch')

        st.markdown(f'<h3><i class="fas fa-phone" style="color: #27ae60;"></i> Call Details ({len(calls)} calls)</h3>', unsafe_allow_html=True)

        # Show all calls for this stage
        for call in sorted(calls, key=lambda c: c.call_date, reverse=True):
            with st.expander(
                f"{format_date(call.call_date)} - {call.call_title[:60]}",
                expanded=False
            ):
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.markdown(f"**Sales Rep:** {call.sales_rep_email}")
                    st.markdown(f"**Date:** {format_date(call.call_date)}")

                with col2:
                    st.markdown(f"[🔗 View in Gong]({format_gong_link(call.call_id)})")

                # Show call participants
                participants = repo.get_call_participants(call.call_id)
                if participants:
                    external_participants = [p for p in participants.values() if p.get('affiliation') == 'External']
                    internal_participants = [p for p in participants.values() if p.get('affiliation') == 'Internal']

                    st.markdown(f"**Participants:** {len(internal_participants)} Internal, {len(external_participants)} External")

                    # Show external participants (customers)
                    if external_participants:
                        with st.expander(f"Customer Attendees ({len(external_participants)})", expanded=False):
                            for p in external_participants:
                                name = p.get('name', 'Unknown')
                                title = p.get('title', '')
                                email = p.get('email_address', '')
                                st.markdown(f"• **{name}** {f'({title})' if title else ''}")
                                if email:
                                    st.markdown(f"  _{email}_")

                st.markdown("---")

                # Show stage-specific details
                if stage_name == "discovery" and hasattr(call, 'meddpicc_scores'):
                    scores = call.meddpicc_scores

                    # Scores card
                    with st.container(border=True):
                        st.markdown('<h3><i class="fas fa-chart-line" style="color: #3498db;"></i> MEDDPICC Scores</h3>', unsafe_allow_html=True)

                        # Overall score with color
                        score_color = get_score_color(scores.overall_score)
                        st.markdown(f"<h2 style='color: {score_color}; margin: 0;'>{scores.overall_score:.1f}/5.0</h2>", unsafe_allow_html=True)
                        st.markdown("")

                        # Dimension breakdown
                        st.markdown("**Dimensions:**")
                        cols = st.columns(4)
                        dimensions = [
                            ("Metrics", scores.metrics),
                            ("Economic Buyer", scores.economic_buyer),
                            ("Decision Criteria", scores.decision_criteria),
                            ("Decision Process", scores.decision_process),
                            ("Paper Process", scores.paper_process),
                            ("Identify Pain", scores.identify_pain),
                            ("Champion", scores.champion),
                            ("Competition", scores.competition)
                        ]
                        for i, (label, score) in enumerate(dimensions):
                            with cols[i % 4]:
                                dim_color = get_score_color(score)
                                st.markdown(f"<div style='text-align: center;'><small>{label}</small><br><span style='color: {dim_color}; font-size: 1.5em; font-weight: bold;'>{score}</span></div>", unsafe_allow_html=True)

                    # Insights card
                    if any([scores.meddpicc_summary, scores.key_gaps, scores.clarity_of_need,
                           scores.key_influencers, scores.next_steps, scores.trial_readiness]):
                        with st.container(border=True):
                            st.markdown('<h3><i class="fas fa-lightbulb" style="color: #f39c12;"></i> Insights & Analysis</h3>', unsafe_allow_html=True)

                            if scores.meddpicc_summary:
                                st.markdown("**Summary**")
                                st.info(scores.meddpicc_summary)

                            if scores.key_gaps:
                                st.markdown("**Key Gaps**")
                                st.warning(scores.key_gaps)

                            if scores.clarity_of_need:
                                st.markdown("**Clarity of Need**")
                                st.markdown(scores.clarity_of_need)

                            if scores.key_influencers:
                                st.markdown("**Key Influencers**")
                                st.markdown(scores.key_influencers)

                            if scores.next_steps:
                                st.markdown("**Next Steps**")
                                st.success(scores.next_steps)

                            if scores.trial_readiness:
                                st.markdown("**Trial Readiness**")
                                st.markdown(scores.trial_readiness)

                elif stage_name == "trial" and hasattr(call, 'trial_scores'):
                    scores = call.trial_scores

                    # Scores card
                    with st.container(border=True):
                        st.markdown('<h3><i class="fas fa-flask" style="color: #9b59b6;"></i> TRIAL Health Scores</h3>', unsafe_allow_html=True)

                        # Overall score with health indicator
                        health_emoji = HEALTH_EMOJIS.get(scores.health_interpretation or "unknown", "⚪")
                        score_color = get_score_color(scores.overall_score)

                        col1, col2 = st.columns([1, 1])
                        with col1:
                            st.markdown(f"<h2 style='color: {score_color}; margin: 0;'>{scores.overall_score:.1f}/5.0</h2>", unsafe_allow_html=True)
                        with col2:
                            st.markdown(f"**Health:** {health_emoji} {(scores.health_interpretation or 'unknown').title()}")
                            st.markdown(f"**Likelihood:** {(scores.likelihood_to_advance or 'unknown').title()}")

                        st.markdown("")

                        # Dimension breakdown
                        st.markdown("**Dimensions:**")
                        cols = st.columns(5)
                        dimensions = [
                            ("Technical", scores.technical_validation),
                            ("Readiness", scores.readiness_progress),
                            ("Adoption", scores.internal_adoption),
                            ("Advocacy", scores.advocacy_sentiment),
                            ("Landscape", scores.landscape_competition)
                        ]
                        for i, (label, score) in enumerate(dimensions):
                            with cols[i]:
                                dim_color = get_score_color(score)
                                st.markdown(f"<div style='text-align: center;'><small>{label}</small><br><span style='color: {dim_color}; font-size: 1.5em; font-weight: bold;'>{score}</span></div>", unsafe_allow_html=True)

                    # Insights card
                    if any([scores.is_bake_off, scores.primary_concern_category, scores.key_concerns,
                           scores.recommended_actions, scores.next_steps]):
                        with st.container(border=True):
                            st.markdown('<h3><i class="fas fa-lightbulb" style="color: #f39c12;"></i> Insights & Actions</h3>', unsafe_allow_html=True)

                            if scores.is_bake_off:
                                st.error("⚠️ **This is a competitive bake-off**")

                            if scores.primary_concern_category:
                                concern_col1, concern_col2 = st.columns(2)
                                with concern_col1:
                                    st.markdown(f"**Primary Concern:** {scores.primary_concern_category.title()}")
                                with concern_col2:
                                    if scores.concern_severity:
                                        st.markdown(f"**Severity:** {scores.concern_severity.title()}")

                            if scores.key_concerns:
                                st.markdown("**Key Concerns**")
                                st.warning(scores.key_concerns)

                            if scores.recommended_actions:
                                st.markdown("**Recommended Actions**")
                                st.info(scores.recommended_actions)

                            if scores.next_steps:
                                st.markdown("**Next Steps**")
                                st.success(scores.next_steps)

                elif stage_name == "negotiation" and hasattr(call, 'close_scores'):
                    scores = call.close_scores

                    # Scores card
                    with st.container(border=True):
                        st.markdown('<h3><i class="fas fa-briefcase" style="color: #e67e22;"></i> CLOSE Health Scores</h3>', unsafe_allow_html=True)

                        # Overall score with health indicator
                        health_emoji = HEALTH_EMOJIS.get(scores.health_interpretation or "unknown", "⚪")
                        score_color = get_score_color(scores.overall_score)

                        col1, col2 = st.columns([1, 1])
                        with col1:
                            st.markdown(f"<h2 style='color: {score_color}; margin: 0;'>{scores.overall_score:.1f}/5.0</h2>", unsafe_allow_html=True)
                        with col2:
                            st.markdown(f"**Health:** {health_emoji} {(scores.health_interpretation or 'unknown').title()}")
                            st.markdown(f"**Likelihood to Close:** {(scores.likelihood_to_close or 'unknown').title()}")

                        st.markdown("")

                        # Dimension breakdown
                        st.markdown("**Dimensions:**")
                        cols = st.columns(5)
                        dimensions = [
                            ("Commercial", scores.commercial_alignment),
                            ("Legal", scores.legal_compliance),
                            ("Consensus", scores.organizational_consensus),
                            ("Threading", scores.single_threading_risk),
                            ("Momentum", scores.execution_momentum)
                        ]
                        for i, (label, score) in enumerate(dimensions):
                            with cols[i]:
                                dim_color = get_score_color(score)
                                st.markdown(f"<div style='text-align: center;'><small>{label}</small><br><span style='color: {dim_color}; font-size: 1.5em; font-weight: bold;'>{score}</span></div>", unsafe_allow_html=True)

                    # Insights card
                    if any([scores.has_competitive_pressure, scores.primary_concern_category, scores.key_concerns,
                           scores.recommended_actions, scores.next_steps]):
                        with st.container(border=True):
                            st.markdown('<h3><i class="fas fa-lightbulb" style="color: #f39c12;"></i> Insights & Actions</h3>', unsafe_allow_html=True)

                            if scores.has_competitive_pressure:
                                st.error("⚠️ **Competitive pressure present**")

                            if scores.primary_concern_category:
                                concern_col1, concern_col2 = st.columns(2)
                                with concern_col1:
                                    st.markdown(f"**Primary Concern:** {scores.primary_concern_category.title()}")
                                with concern_col2:
                                    if scores.concern_severity:
                                        st.markdown(f"**Severity:** {scores.concern_severity.title()}")

                            if scores.key_concerns:
                                st.markdown("**Key Concerns**")
                                st.warning(scores.key_concerns)

                            if scores.recommended_actions:
                                st.markdown("**Recommended Actions**")
                                st.info(scores.recommended_actions)

                            if scores.next_steps:
                                st.markdown("**Next Steps**")
                                st.success(scores.next_steps)

                elif stage_name == "closed" and hasattr(call, 'winloss_analysis'):
                    analysis = call.winloss_analysis

                    # Outcome card
                    with st.container(border=True):
                        outcome_emoji = OUTCOME_EMOJIS.get(analysis.outcome, "⚪")
                        outcome_color = "#2ecc71" if analysis.outcome == "won" else "#e74c3c"

                        st.markdown(f"<h2 style='color: {outcome_color}; margin: 0;'>{outcome_emoji} Deal {analysis.outcome.title()}</h2>", unsafe_allow_html=True)

                        if analysis.stage_of_decision:
                            st.markdown(f"**Stage of Decision:** {analysis.stage_of_decision.title()}")

                    # Analysis card
                    if any([analysis.primary_reasons, analysis.critical_dimensions, analysis.competitive_factor,
                           analysis.key_learnings, analysis.verbatim_quotes]):
                        with st.container(border=True):
                            st.markdown('<h3><i class="fas fa-clipboard-check" style="color: #3498db;"></i> Win/Loss Analysis</h3>', unsafe_allow_html=True)

                            if analysis.primary_reasons:
                                st.markdown("**Primary Reasons**")
                                if analysis.outcome == "won":
                                    st.success(analysis.primary_reasons)
                                else:
                                    st.error(analysis.primary_reasons)

                            if analysis.critical_dimensions:
                                st.markdown("**Critical Dimensions**")
                                st.info(analysis.critical_dimensions)

                            if analysis.competitive_factor:
                                st.markdown("**Competitive Factor**")
                                st.warning(analysis.competitive_factor)

                            if analysis.key_learnings:
                                st.markdown("**Key Learnings**")
                                st.markdown(analysis.key_learnings)

                            if analysis.verbatim_quotes:
                                st.markdown("**Verbatim Quotes**")
                                st.markdown(f"_{analysis.verbatim_quotes}_")

        st.markdown("---")


# ============================================================================
# Main App
# ============================================================================

def main():
    """Main multi-stage account dashboard."""

    # Load Font Awesome
    st.markdown("""
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    """, unsafe_allow_html=True)

    st.markdown('<h1 style="margin-bottom: 0;"><i class="fas fa-building" style="color: #3498db;"></i> Account Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color: #7f8c8d; margin-top: 0; margin-bottom: 1rem;">Track accounts across discovery, trial, negotiation, and closed stages</p>', unsafe_allow_html=True)
    st.markdown("---")

    # Load segments from database first
    config = Config()
    db = Database(config.SQLITE_DB_PATH)
    db.connect()
    repo = Repository(db.conn)

    try:
        sales_reps = repo.list_sales_reps()
        segments = sorted(set(rep.segment for rep in sales_reps if rep.segment))
    finally:
        db.close()

    # Sidebar filters
    st.sidebar.header("⚙️ Filters")

    # Segment filter (dynamically loaded from database)
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

    st.sidebar.markdown("---")

    # Load data
    with st.spinner("Loading accounts..."):
        accounts, segments = load_data(
            stage=stage_selection if stage_selection != "All" else None,
            segment=segment_selection.lower() if segment_selection != "All" else None
        )

    if not accounts:
        st.warning("No accounts found with the selected filters.")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
            <div style="text-align: center; padding: 10px;">
                <p style="color: #7f8c8d; font-size: 0.9rem; margin-bottom: 5px;">
                    <i class="fas fa-building" style="color: #3498db;"></i> Total Accounts
                </p>
                <p style="font-size: 2rem; font-weight: bold; margin: 0;">{len(accounts)}</p>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        discovery_count = sum(1 for a in accounts if a.current_stage == "discovery")
        st.markdown(f"""
            <div style="text-align: center; padding: 10px;">
                <p style="color: #7f8c8d; font-size: 0.9rem; margin-bottom: 5px;">
                    <i class="fas fa-search" style="color: #3498db;"></i> Discovery
                </p>
                <p style="font-size: 2rem; font-weight: bold; margin: 0;">{discovery_count}</p>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        trial_count = sum(1 for a in accounts if a.current_stage == "trial")
        st.markdown(f"""
            <div style="text-align: center; padding: 10px;">
                <p style="color: #7f8c8d; font-size: 0.9rem; margin-bottom: 5px;">
                    <i class="fas fa-flask" style="color: #9b59b6;"></i> Trial
                </p>
                <p style="font-size: 2rem; font-weight: bold; margin: 0;">{trial_count}</p>
            </div>
        """, unsafe_allow_html=True)

    with col4:
        negotiation_count = sum(1 for a in accounts if a.current_stage == "negotiation")
        st.markdown(f"""
            <div style="text-align: center; padding: 10px;">
                <p style="color: #7f8c8d; font-size: 0.9rem; margin-bottom: 5px;">
                    <i class="fas fa-briefcase" style="color: #e67e22;"></i> Negotiation
                </p>
                <p style="font-size: 2rem; font-weight: bold; margin: 0;">{negotiation_count}</p>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Custom CSS for larger tab labels
    st.markdown("""
        <style>
        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
            font-size: 1.2rem;
            font-weight: 600;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 2rem;
        }
        </style>
    """, unsafe_allow_html=True)

    # === VIEW TOGGLE: CHART vs TABLE ===
    view_tab1, view_tab2 = st.tabs([
        "Chart View",
        "Table View"
    ])

    # Add icons to tabs via CSS (workaround since tabs don't support HTML)
    st.markdown("""
        <style>
        /* Add Font Awesome icons before tab labels with spacing */
        .stTabs [data-baseweb="tab-list"] button:nth-child(1)::before {
            content: "\\f080";
            font-family: "Font Awesome 6 Free";
            font-weight: 900;
            color: #2ecc71;
            margin-right: 8px;
        }
        .stTabs [data-baseweb="tab-list"] button:nth-child(2)::before {
            content: "\\f0ce";
            font-family: "Font Awesome 6 Free";
            font-weight: 900;
            color: #3498db;
            margin-right: 8px;
        }
        </style>
    """, unsafe_allow_html=True)

    # === TAB 1: STAGE HEALTH VISUALIZATION ===
    with view_tab1:
        st.markdown("*Bubble size = total calls | Color = health score (🟢 ≥4, 🟡 2-4, 🔴 <2) | Click bubble to view details*")
        st.markdown("")

        config = Config()
        db = Database(config.SQLITE_DB_PATH)
        db.connect()
        repo = Repository(db.conn)

        try:
            # Store bubble data in session state for click handling
            if 'bubble_data_discovery' not in st.session_state:
                st.session_state.bubble_data_discovery = []
            if 'bubble_data_trial' not in st.session_state:
                st.session_state.bubble_data_trial = []

            # 2 bubble charts: Discovery and Trial (Negotiation moves fast - win or lose)
            col1, col2 = st.columns(2)

            # Discovery
            with col1:
                bubble_data_discovery = get_stage_bubble_data(
                    repo,
                    segment=segment_selection if segment_selection != "All" else None,
                    stage="discovery"
                )
                st.session_state.bubble_data_discovery = bubble_data_discovery
                bubble_fig_discovery = create_bubble_scatter_chart(bubble_data_discovery, "discovery", "🔍")

                discovery_event = st.plotly_chart(
                    bubble_fig_discovery,
                    width='stretch',
                    key="bubble_discovery",
                    on_select="rerun",
                    selection_mode="points"
                )

                # Handle bubble click for Discovery
                if discovery_event and discovery_event.selection and discovery_event.selection.points:
                    points = discovery_event.selection.points
                    if points and len(points) > 0:
                        # Get domain from customdata (more reliable than point_index with multiple traces)
                        clicked_domain = points[0].get('customdata')
                        if clicked_domain:
                            st.session_state['selected_account_domain_main'] = clicked_domain

            # Trial
            with col2:
                bubble_data_trial = get_stage_bubble_data(
                    repo,
                    segment=segment_selection if segment_selection != "All" else None,
                    stage="trial"
                )
                st.session_state.bubble_data_trial = bubble_data_trial
                bubble_fig_trial = create_bubble_scatter_chart(bubble_data_trial, "trial", "🧪")

                trial_event = st.plotly_chart(
                    bubble_fig_trial,
                    width='stretch',
                    key="bubble_trial",
                    on_select="rerun",
                    selection_mode="points"
                )

                # Handle bubble click for Trial
                if trial_event and trial_event.selection and trial_event.selection.points:
                    points = trial_event.selection.points
                    if points and len(points) > 0:
                        # Get domain from customdata (more reliable than point_index with multiple traces)
                        clicked_domain = points[0].get('customdata')
                        if clicked_domain:
                            st.session_state['selected_account_domain_main'] = clicked_domain

        finally:
            db.close()

    # === TAB 2: TABLE VIEW ===
    with view_tab2:
        config = Config()
        db = Database(config.SQLITE_DB_PATH)
        db.connect()
        repo = Repository(db.conn)

        try:
            table_data = build_table_data(accounts, stage_selection, repo)

            if not table_data:
                st.info("No accounts with calls in the selected stage.")
                return

            # Convert to DataFrame
            df = pd.DataFrame(table_data)

            # Remove internal columns for display
            display_columns = [col for col in df.columns if not col.startswith('_')]
            display_df = df[display_columns]

            # Display table with AG Grid
            st.markdown("**Click on a row to view account details**")

            # Configure AG Grid
            gb = GridOptionsBuilder.from_dataframe(display_df)
            gb.configure_default_column(
                filterable=True,
                sortable=True,
                resizable=True,
                filter=True
            )
            gb.configure_selection(
                selection_mode='single',
                use_checkbox=False,
                header_checkbox=False
            )

            # Hide gong_link column (used for rendering)
            gb.configure_column("gong_link", hide=True)

            # Configure column widths
            gb.configure_column("Account", width=150)
            gb.configure_column("Stage", width=120)
            gb.configure_column("Segment", width=100)
            gb.configure_column("Sales Rep", width=120)
            gb.configure_column("# Calls", width=80)
            gb.configure_column("Days in Stage", width=120)
            gb.configure_column("Last Call", width=120)
            gb.configure_column("Score", width=80)
            gb.configure_column("Key Gap", width=200)
            gb.configure_column("Primary Concern", width=150)

            # Make Call Title clickable - style it like a link and handle clicks
            gb.configure_column(
                "Call Title",
                flex=1,
                minWidth=300,
                cellStyle={'color': '#1a73e8', 'textDecoration': 'underline', 'cursor': 'pointer'}
            )

            # Configure pagination
            gb.configure_pagination(
                enabled=True,
                paginationPageSize=50
            )

            # Enable filtering in header
            gb.configure_side_bar(
                filters_panel=True,
                columns_panel=False
            )

            # Build grid options
            grid_options = gb.build()

            # Add cell click handler for Call Title
            grid_options['onCellClicked'] = JsCode("""
                function(params) {
                    if (params.column.colId === 'Call Title' && params.data.gong_link) {
                        window.open(params.data.gong_link, '_blank');
                    }
                }
            """)

            # Display AG Grid
            grid_response = AgGrid(
                display_df,
                gridOptions=grid_options,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                fit_columns_on_grid_load=False,
                theme='streamlit',
                height=600,
                allow_unsafe_jscode=True,
                reload_data=False,
                enable_enterprise_modules=False
            )

            st.markdown(f"**Showing {len(table_data)} account(s)**")

            # Handle row selection with AG Grid
            selected_rows = grid_response['selected_rows']
            if selected_rows is not None and len(selected_rows) > 0:
                # selected_rows is a DataFrame, use iloc to get first row
                selected_row = selected_rows.iloc[0]
                selected_account_domain = selected_row['Account']
                st.session_state['selected_account_domain_main'] = selected_account_domain

        finally:
            db.close()

    # === ACCOUNT DETAILS (Outside tabs - shown for both bubble and table clicks) ===
    if 'selected_account_domain_main' in st.session_state:
        st.markdown("---")
        st.markdown('<h2><i class="fas fa-book-open" style="color: #3498db;"></i> Account Details</h2>', unsafe_allow_html=True)

        selected_account = next(
            (a for a in accounts if a.domain == st.session_state['selected_account_domain_main']),
            None
        )

        if selected_account:
            config = Config()
            db = Database(config.SQLITE_DB_PATH)
            db.connect()
            repo = Repository(db.conn)

            try:
                show_account_detail(selected_account, repo)
            finally:
                db.close()
        else:
            st.warning(f"Account {st.session_state['selected_account_domain_main']} not found in current filter.")


if __name__ == "__main__":
    main()
