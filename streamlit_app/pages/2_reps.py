"""Reps Dashboard - Compare sales rep performance and identify coaching opportunities."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Add pages directory to path for cross-page imports
pages_dir = Path(__file__).parent
sys.path.insert(0, str(pages_dir))

from src.core import Config
from src.data import Database, Repository
from src.domain import Call

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

    for rep in rep_data:
        row = {
            "Rep": rep["name"],
            "Segment": rep["segment"],
            "Calls": rep["total_calls"],
            "Accounts": rep["total_accounts"],
            "Discovery Avg": f"{rep['discovery_avg']:.1f}" if rep['discovery_avg'] is not None else "N/A",
            "Trial Avg": f"{rep['trial_avg']:.1f}" if rep['trial_avg'] is not None else "N/A",
            "Negotiation Avg": f"{rep['negotiation_avg']:.1f}" if rep['negotiation_avg'] is not None else "N/A",
            "Active Deals": rep["active_deals"],
            "_email": rep["email"]
        }
        table_data.append(row)

    return table_data


# ============================================================================
# Call Detail View
# ============================================================================

def show_call_detail(call: Call, repo: Repository):
    """Show detailed analysis for a single call."""
    # Get account info
    account = repo.get_account(call.account_id)
    account_domain = account.domain if account else "Unknown"

    # Stage emoji
    stage_emojis = {
        "discovery": "🔍",
        "trial": "🧪",
        "negotiation": "💼",
        "closed": "✅"
    }
    stage_emoji = stage_emojis.get(call.primary_stage, "📊")

    # Header
    st.markdown(f"## {stage_emoji} {call.call_title}")

    # Metadata row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Account:** {account_domain}")
    with col2:
        st.markdown(f"**Date:** {format_date(call.call_date)}")
    with col3:
        st.markdown(f"**Stage:** {call.primary_stage.title()}")

    # Gong link
    gong_link = format_gong_link(call.call_id)
    st.markdown(f"[🔗 Open in Gong]({gong_link})")

    # Get participants
    cursor = repo.conn.execute(
        "SELECT * FROM call_participants WHERE call_id = ?",
        (call.call_id,)
    )
    participants = cursor.fetchall()

    if participants:
        external_participants = [p for p in participants if p['affiliation'] == 'External']
        internal_participants = [p for p in participants if p['affiliation'] == 'Internal']

        st.markdown(f"**Participants:** {len(internal_participants)} Internal, {len(external_participants)} External")

        # Show participants in expandable section
        with st.expander(f"👥 Call Attendees ({len(participants)} total)", expanded=False):
            if internal_participants:
                st.markdown("**Internal:**")
                for p in internal_participants:
                    try:
                        name = p['name'] if p['name'] else 'Unknown'
                    except (KeyError, TypeError):
                        name = 'Unknown'

                    try:
                        email = p['email_address'] if p['email_address'] else ''
                    except (KeyError, TypeError):
                        email = ''

                    st.markdown(f"• {name} {f'({email})' if email else ''}")

            if external_participants:
                st.markdown("**Customer:**")
                for p in external_participants:
                    try:
                        name = p['name'] if p['name'] else 'Unknown'
                    except (KeyError, TypeError):
                        name = 'Unknown'

                    try:
                        title = p['title'] if p['title'] else ''
                    except (KeyError, TypeError):
                        title = ''

                    try:
                        persona = f" ({p['persona']})" if p['persona'] else ""
                    except (KeyError, TypeError):
                        persona = ""

                    st.markdown(f"• **{name}** {f'({title})' if title else ''}{persona}")

    st.markdown("---")

    # Show scores based on stage
    if call.primary_stage == "discovery":
        scores = repo.get_call_meddpicc_scores(call.call_id)
        if scores:
            # Overall score
            st.metric("MEDDPICC Score", f"{scores.scores.overall_score:.1f}/5.0")

            # Dimension breakdown
            st.markdown("**Dimension Scores:**")
            cols = st.columns(4)
            dimensions = [
                ("Metrics", scores.scores.metrics),
                ("Econ Buyer", scores.scores.economic_buyer),
                ("Dec Criteria", scores.scores.decision_criteria),
                ("Dec Process", scores.scores.decision_process),
                ("Paper Process", scores.scores.paper_process),
                ("Pain", scores.scores.identify_pain),
                ("Champion", scores.scores.champion),
                ("Competition", scores.scores.competition)
            ]
            for i, (label, score) in enumerate(dimensions):
                cols[i % 4].metric(label, f"{score}/5")

            # Show analysis
            if scores.scores.meddpicc_summary:
                st.markdown("**Summary:**")
                st.markdown(f"> {scores.scores.meddpicc_summary}")

            if scores.scores.key_gaps:
                st.markdown("**Key Gaps:**")
                st.markdown(f"> {scores.scores.key_gaps}")

            if scores.scores.clarity_of_need:
                st.markdown("**Clarity of Need:**")
                st.markdown(f"> {scores.scores.clarity_of_need}")

            if scores.scores.key_influencers:
                st.markdown("**Key Influencers:**")
                st.markdown(f"> {scores.scores.key_influencers}")

            if scores.scores.next_steps:
                st.markdown("**Next Steps:**")
                st.markdown(f"> {scores.scores.next_steps}")

            if scores.scores.trial_readiness:
                st.markdown("**Trial Readiness:**")
                st.markdown(f"> {scores.scores.trial_readiness}")

    elif call.primary_stage == "trial":
        scores = repo.get_call_trial_scores(call.call_id)
        if scores:
            # Overall score
            health_emoji = {"healthy": "✅", "at_risk": "⚠️", "critical": "🔴"}.get(scores.scores.health_interpretation or "unknown", "⚪")
            st.metric("Trial Health Score", f"{scores.scores.overall_score:.1f}/5.0")
            st.markdown(f"**Health:** {health_emoji} {(scores.scores.health_interpretation or 'unknown').title()}")
            if scores.scores.likelihood_to_advance:
                st.markdown(f"**Likelihood to Advance:** {scores.scores.likelihood_to_advance.title()}")

            # Dimension breakdown
            st.markdown("**Dimension Scores:**")
            cols = st.columns(5)
            cols[0].metric("Tech Valid", f"{scores.scores.technical_validation}/5")
            cols[1].metric("Readiness", f"{scores.scores.readiness_progress}/5")
            cols[2].metric("Adoption", f"{scores.scores.internal_adoption}/5")
            cols[3].metric("Advocacy", f"{scores.scores.advocacy_sentiment}/5")
            cols[4].metric("Landscape", f"{scores.scores.landscape_competition}/5")

            # Show concerns
            if scores.scores.primary_concern_category and scores.scores.primary_concern_category != "none":
                st.markdown(f"**Primary Concern:** {scores.scores.primary_concern_category.title()}")

            if scores.scores.concern_severity:
                st.markdown(f"**Concern Severity:** {scores.scores.concern_severity.title()}")

            if scores.scores.is_bake_off:
                st.warning("⚠️ **This is a competitive bake-off**")

            if scores.scores.key_concerns:
                st.markdown("**Key Concerns:**")
                st.markdown(f"> {scores.scores.key_concerns}")

            if scores.scores.recommended_actions:
                st.markdown("**Recommended Actions:**")
                st.markdown(f"> {scores.scores.recommended_actions}")

            if scores.scores.next_steps:
                st.markdown("**Next Steps:**")
                st.markdown(f"> {scores.scores.next_steps}")

    elif call.primary_stage == "negotiation":
        scores = repo.get_call_close_scores(call.call_id)
        if scores:
            # Overall score
            health_emoji = {"healthy": "✅", "at_risk": "⚠️", "critical": "🔴"}.get(scores.scores.health_interpretation or "unknown", "⚪")
            st.metric("Deal Health Score", f"{scores.scores.overall_score:.1f}/5.0")
            st.markdown(f"**Health:** {health_emoji} {(scores.scores.health_interpretation or 'unknown').title()}")
            if scores.scores.likelihood_to_close:
                st.markdown(f"**Likelihood to Close:** {scores.scores.likelihood_to_close.title()}")

            # Dimension breakdown
            st.markdown("**Dimension Scores:**")
            cols = st.columns(5)
            cols[0].metric("Commercial", f"{scores.scores.commercial_alignment}/5")
            cols[1].metric("Legal", f"{scores.scores.legal_compliance}/5")
            cols[2].metric("Consensus", f"{scores.scores.organizational_consensus}/5")
            cols[3].metric("Threading", f"{scores.scores.single_threading_risk}/5")
            cols[4].metric("Momentum", f"{scores.scores.execution_momentum}/5")

            # Show concerns
            if scores.scores.primary_concern_category and scores.scores.primary_concern_category != "none":
                st.markdown(f"**Primary Concern:** {scores.scores.primary_concern_category.title()}")

            if scores.scores.concern_severity:
                st.markdown(f"**Concern Severity:** {scores.scores.concern_severity.title()}")

            if scores.scores.has_competitive_pressure:
                st.warning("⚠️ **Competitive pressure present**")

            if scores.scores.key_concerns:
                st.markdown("**Key Concerns:**")
                st.markdown(f"> {scores.scores.key_concerns}")

            if scores.scores.recommended_actions:
                st.markdown("**Recommended Actions:**")
                st.markdown(f"> {scores.scores.recommended_actions}")

            if scores.scores.next_steps:
                st.markdown("**Next Steps:**")
                st.markdown(f"> {scores.scores.next_steps}")


# ============================================================================
# Recommended Calls
# ============================================================================

def get_recommended_calls_for_rep(repo: Repository, rep_email: str, rep_segment: str,
                                   date_from: Optional[datetime] = None,
                                   date_to: Optional[datetime] = None) -> List[tuple]:
    """Find exemplar calls for rep's weak dimensions."""

    # Get rep's dimension scores by stage
    rep_scores = {
        'discovery': {},
        'trial': {},
        'negotiation': {}
    }

    # Build query for rep's calls
    query_parts = ["SELECT * FROM calls WHERE sales_rep_email = ?"]
    params = [rep_email]

    if date_from:
        query_parts.append("AND call_date >= ?")
        params.append(date_from)
    if date_to:
        query_parts.append("AND call_date <= ?")
        params.append(date_to)

    query = " ".join(query_parts)
    cursor = repo.conn.execute(query, params)
    rep_call_rows = cursor.fetchall()

    # Calculate rep's dimension averages
    discovery_dims = defaultdict(list)
    trial_dims = defaultdict(list)
    negotiation_dims = defaultdict(list)

    for call_row in rep_call_rows:
        call = repo._row_to_call(call_row)

        if call.primary_stage == "discovery":
            scores = repo.get_call_meddpicc_scores(call.call_id)
            if scores:
                s = scores.scores
                discovery_dims['metrics'].append(s.metrics)
                discovery_dims['economic_buyer'].append(s.economic_buyer)
                discovery_dims['decision_criteria'].append(s.decision_criteria)
                discovery_dims['decision_process'].append(s.decision_process)
                discovery_dims['paper_process'].append(s.paper_process)
                discovery_dims['identify_pain'].append(s.identify_pain)
                discovery_dims['champion'].append(s.champion)
                discovery_dims['competition'].append(s.competition)

        elif call.primary_stage == "trial":
            scores = repo.get_call_trial_scores(call.call_id)
            if scores:
                s = scores.scores
                trial_dims['technical_validation'].append(s.technical_validation)
                trial_dims['readiness_progress'].append(s.readiness_progress)
                trial_dims['internal_adoption'].append(s.internal_adoption)
                trial_dims['advocacy_sentiment'].append(s.advocacy_sentiment)
                trial_dims['landscape_competition'].append(s.landscape_competition)

        elif call.primary_stage == "negotiation":
            scores = repo.get_call_close_scores(call.call_id)
            if scores:
                s = scores.scores
                negotiation_dims['commercial_alignment'].append(s.commercial_alignment)
                negotiation_dims['legal_compliance'].append(s.legal_compliance)
                negotiation_dims['organizational_consensus'].append(s.organizational_consensus)
                negotiation_dims['single_threading_risk'].append(s.single_threading_risk)
                negotiation_dims['execution_momentum'].append(s.execution_momentum)

    # Calculate averages and identify weak dimensions
    weak_dimensions = []

    for stage, dims_dict in [('discovery', discovery_dims), ('trial', trial_dims), ('negotiation', negotiation_dims)]:
        for dim_key, scores in dims_dict.items():
            if scores:
                avg = sum(scores) / len(scores)
                if avg < 3.5:  # Weak dimension
                    weak_dimensions.append((stage, dim_key, avg))

    # Sort by score (weakest first) and take top 3
    weak_dimensions.sort(key=lambda x: x[2])
    weak_dimensions = weak_dimensions[:3]

    if not weak_dimensions:
        return []

    # Find high-scoring calls for weak dimensions
    # Collect up to 2-3 calls per weak dimension to ensure coverage across stages
    # Returns list of tuples: (call, dimension_display_name, dimension_score)
    recommended_calls = []
    seen_call_ids = set()
    calls_per_dimension = 2  # Max 2 calls per weak dimension

    # Dimension key to display name mapping
    dimension_display_names = {
        # Discovery
        'metrics': 'Metrics',
        'economic_buyer': 'Economic Buyer',
        'decision_criteria': 'Decision Criteria',
        'decision_process': 'Decision Process',
        'paper_process': 'Paper Process',
        'identify_pain': 'Identify Pain',
        'champion': 'Champion',
        'competition': 'Competition',
        # Trial
        'technical_validation': 'Technical Validation',
        'readiness_progress': 'Readiness & Progress',
        'internal_adoption': 'Internal Adoption',
        'advocacy_sentiment': 'Advocacy & Sentiment',
        'landscape_competition': 'Landscape & Competition',
        # Negotiation
        'commercial_alignment': 'Commercial Alignment',
        'legal_compliance': 'Legal & Compliance',
        'organizational_consensus': 'Organizational Consensus',
        'single_threading_risk': 'Single-Threading Risk',
        'execution_momentum': 'Execution Momentum'
    }

    for stage, dim_key, _ in weak_dimensions:
        dimension_calls = []
        dimension_display_name = dimension_display_names.get(dim_key, dim_key.replace('_', ' ').title())

        # Query for high-scoring calls in same segment
        query_parts = ["""
            SELECT c.* FROM calls c
            JOIN accounts a ON c.account_id = a.id
            WHERE c.primary_stage = ?
            AND a.primary_segment = ?
        """]
        params = [stage, rep_segment.lower()]

        if date_from:
            query_parts.append("AND c.call_date >= ?")
            params.append(date_from)
        if date_to:
            query_parts.append("AND c.call_date <= ?")
            params.append(date_to)

        query_parts.append("ORDER BY c.call_date DESC")
        query = " ".join(query_parts)

        cursor = repo.conn.execute(query, params)
        candidate_rows = cursor.fetchall()

        # Filter for high scores on this dimension
        for call_row in candidate_rows:
            call = repo._row_to_call(call_row)

            if call.call_id in seen_call_ids:
                continue

            dim_score = None

            if stage == "discovery":
                scores = repo.get_call_meddpicc_scores(call.call_id)
                if scores:
                    dim_score = getattr(scores.scores, dim_key, None)
            elif stage == "trial":
                scores = repo.get_call_trial_scores(call.call_id)
                if scores:
                    dim_score = getattr(scores.scores, dim_key, None)
            elif stage == "negotiation":
                scores = repo.get_call_close_scores(call.call_id)
                if scores:
                    dim_score = getattr(scores.scores, dim_key, None)

            if dim_score is not None and dim_score >= 4.5:
                # Store as tuple: (call, dimension_name, dimension_score)
                dimension_calls.append((call, dimension_display_name, dim_score))
                seen_call_ids.add(call.call_id)

                # Limit calls per dimension
                if len(dimension_calls) >= calls_per_dimension:
                    break

        # Add this dimension's calls to overall list
        recommended_calls.extend(dimension_calls)

    # Return up to 10 calls total (allows for 3 dimensions x 2-3 calls each)
    return recommended_calls[:10]


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

    # Recommended calls to review
    st.markdown("### 📚 Recommended Calls To Review")

    # Get weak dimensions for context
    rep_segment = rep.segment or "enterprise"

    # Calculate weak dimensions to show what we're targeting
    weak_dims_info = []

    # Discovery dimensions
    if discovery_dimension_scores:
        dim_avgs = {dim: sum(scores) / len(scores) for dim, scores in discovery_dimension_scores.items()}
        for dim, avg in dim_avgs.items():
            if avg < 3.5:
                weak_dims_info.append(f"{dim} (Discovery: {avg:.1f})")

    # Trial dimensions
    if trial_dimension_scores:
        dim_avgs = {dim: sum(scores) / len(scores) for dim, scores in trial_dimension_scores.items()}
        for dim, avg in dim_avgs.items():
            if avg < 3.5:
                weak_dims_info.append(f"{dim} (Trial: {avg:.1f})")

    # Negotiation dimensions
    if negotiation_dimension_scores:
        dim_avgs = {dim: sum(scores) / len(scores) for dim, scores in negotiation_dimension_scores.items()}
        for dim, avg in dim_avgs.items():
            if avg < 3.5:
                weak_dims_info.append(f"{dim} (Negotiation: {avg:.1f})")

    if weak_dims_info:
        st.markdown(f"**Growth areas:** {', '.join(weak_dims_info[:3])}")

    st.markdown(f"Showing high-scoring calls from **{rep_segment.title()}** segment")

    recommended_calls = get_recommended_calls_for_rep(
        repo, rep_email, rep_segment, date_from, date_to
    )

    if recommended_calls:
        # Build table data using same format as Calls page
        # recommended_calls is list of tuples: (call, dimension_name, dimension_score)
        recommended_table_data = []
        for call, target_dimension, dimension_score in recommended_calls:
            # Get account
            account = repo.get_account(call.account_id)
            account_domain = account.domain if account else "Unknown"
            segment = account.primary_segment if account else "unknown"

            # Get sales rep (format email)
            sales_rep = call.sales_rep_email
            if "@" in sales_rep:
                sales_rep = sales_rep.split("@")[0]

            # Get stage with emoji
            stage_emojis = {
                "discovery": "🔍",
                "trial": "🧪",
                "negotiation": "💼",
                "closed": "✅"
            }
            stage_emoji = stage_emojis.get(call.primary_stage, "📊")
            stage = f"{stage_emoji} {call.primary_stage.title()}"

            # Get score
            score = None
            if call.primary_stage == "discovery":
                scores = repo.get_call_meddpicc_scores(call.call_id)
                if scores:
                    score = scores.scores.overall_score
            elif call.primary_stage == "trial":
                scores = repo.get_call_trial_scores(call.call_id)
                if scores:
                    score = scores.scores.overall_score
            elif call.primary_stage == "negotiation":
                scores = repo.get_call_close_scores(call.call_id)
                if scores:
                    score = scores.scores.overall_score

            gong_link = format_gong_link(call.call_id)

            row = {
                "Call Date": format_date(call.call_date),
                "Account": account_domain,
                "Sales Rep": sales_rep,
                "Stage": stage,
                "Score": f"{score:.1f}" if score is not None else "N/A",
                "Strong In": target_dimension,
                "Dimension Score": f"{dimension_score:.1f}",
                "Call Title": call.call_title,
                "gong_link": gong_link,
                "_call_id": call.call_id,
                "_call_date": call.call_date
            }
            recommended_table_data.append(row)

        # Display with AG Grid (same format as Calls page)
        df = pd.DataFrame(recommended_table_data)
        display_columns = [col for col in df.columns if not col.startswith('_')]
        display_df = df[display_columns]

        # Configure AG Grid
        gb = GridOptionsBuilder.from_dataframe(display_df)
        gb.configure_default_column(
            filterable=False,
            sortable=True,
            resizable=True
        )
        gb.configure_selection(
            selection_mode='single',
            use_checkbox=False,
            header_checkbox=False
        )

        # Configure column widths
        gb.configure_column("Call Date", width=110)
        gb.configure_column("Account", width=140)
        gb.configure_column("Sales Rep", width=110)
        gb.configure_column("Stage", width=110)
        gb.configure_column("Score", width=70)
        gb.configure_column("Strong In", width=180)
        gb.configure_column("Dimension Score", width=130)

        # Make Call Title clickable
        gb.configure_column("gong_link", hide=True)
        gb.configure_column(
            "Call Title",
            flex=1,
            minWidth=300,
            cellStyle={'color': '#1a73e8', 'textDecoration': 'underline', 'cursor': 'pointer'}
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
            height=min(400, len(recommended_table_data) * 50 + 100),
            allow_unsafe_jscode=True,
            reload_data=False,
            enable_enterprise_modules=False
        )

        st.markdown(f"*Showing {len(recommended_calls)} recommended call(s). Click a row to view details.*")

        # Handle row selection - show call detail
        selected_rows = grid_response['selected_rows']
        if selected_rows is not None and len(selected_rows) > 0:
            selected_row = selected_rows.iloc[0]
            selected_call_id = None

            # Find the call ID from the original data
            for row in recommended_table_data:
                if (row['Call Date'] == selected_row['Call Date'] and
                    row['Call Title'] == selected_row['Call Title'] and
                    row['Account'] == selected_row['Account']):
                    selected_call_id = row['_call_id']
                    break

            if selected_call_id:
                # Find the call object (recommended_calls contains tuples: (call, dim_name, dim_score))
                selected_call = None
                for call, dim_name, dim_score in recommended_calls:
                    if call.call_id == selected_call_id:
                        selected_call = call
                        break

                if selected_call:
                    st.markdown("---")
                    show_call_detail(selected_call, repo)
    else:
        st.info("No recommended calls found. This rep is performing well across all dimensions!")



# ============================================================================
# Main App
# ============================================================================

def main():
    """Main reps dashboard."""

    # Load Font Awesome
    st.markdown("""
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    """, unsafe_allow_html=True)

    st.markdown('<h1 style="margin-bottom: 0;"><i class="fas fa-users" style="color: #3498db;"></i> Sales Reps Performance</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color: #7f8c8d; margin-top: 0; margin-bottom: 1rem;">Compare sales rep performance and identify coaching opportunities</p>', unsafe_allow_html=True)
    st.markdown("---")

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
        col1, col2, col3, col4 = st.columns(4)

        # Calculate metrics
        total_calls = sum(r["total_calls"] for r in rep_data)
        total_accounts = sum(r["total_accounts"] for r in rep_data)

        # Calculate team average score (across all stages)
        all_scores = []
        for r in rep_data:
            if r["discovery_avg"]:
                all_scores.append(r["discovery_avg"])
            if r["trial_avg"]:
                all_scores.append(r["trial_avg"])
            if r["negotiation_avg"]:
                all_scores.append(r["negotiation_avg"])

        team_avg = sum(all_scores) / len(all_scores) if all_scores else 0
        team_avg_color = "#2ecc71" if team_avg >= 4.0 else "#f39c12" if team_avg >= 2.0 else "#e74c3c"
        team_avg_display = f"{team_avg:.1f}" if team_avg > 0 else "N/A"

        # Calculate calls per rep per day
        if days and len(rep_data) > 0:
            calls_per_rep_day = total_calls / len(rep_data) / days
        else:
            calls_per_rep_day = 0

        with col1:
            st.markdown(f"""
                <div style="text-align: center; padding: 5px;">
                    <p style="color: #7f8c8d; font-size: 0.85rem; margin: 0 0 3px 0;">
                        <i class="fas fa-users" style="color: #3498db;"></i> Active Reps
                    </p>
                    <p style="font-size: 1.8rem; font-weight: bold; margin: 0; line-height: 1;">{len(rep_data)}</p>
                </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
                <div style="text-align: center; padding: 5px;">
                    <p style="color: #7f8c8d; font-size: 0.85rem; margin: 0 0 3px 0;">
                        <i class="fas fa-chart-line" style="color: {team_avg_color};"></i> Avg Team Score
                    </p>
                    <p style="font-size: 1.8rem; font-weight: bold; margin: 0; color: {team_avg_color}; line-height: 1;">{team_avg_display}</p>
                </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
                <div style="text-align: center; padding: 5px;">
                    <p style="color: #7f8c8d; font-size: 0.85rem; margin: 0 0 3px 0;">
                        <i class="fas fa-phone" style="color: #27ae60;"></i> Total Calls
                    </p>
                    <p style="font-size: 1.8rem; font-weight: bold; margin: 0; line-height: 1;">{total_calls}</p>
                </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
                <div style="text-align: center; padding: 5px;">
                    <p style="color: #7f8c8d; font-size: 0.85rem; margin: 0 0 3px 0;">
                        <i class="fas fa-calendar-day" style="color: #9b59b6;"></i> Calls/Rep/Day
                    </p>
                    <p style="font-size: 1.8rem; font-weight: bold; margin: 0; line-height: 1;">{calls_per_rep_day:.1f}</p>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # Team Performance Section
        st.markdown('<h2><i class="fas fa-chart-bar" style="color: #2ecc71;"></i> Team Performance</h2>', unsafe_allow_html=True)
        st.markdown("")

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
            st.plotly_chart(comparison_chart, width="stretch")
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
                st.plotly_chart(heatmap, width="stretch")
            else:
                st.info("No dimension data available for heatmap.")

        st.markdown("---")

        # Reps table
        st.markdown('<h3><i class="fas fa-table" style="color: #3498db;"></i> Rep Performance</h3>', unsafe_allow_html=True)
        table_data = build_reps_table(rep_data)

        if not table_data:
            st.info("No rep data available.")
            return

        # Display table with AG Grid
        df = pd.DataFrame(table_data)
        display_columns = [col for col in df.columns if not col.startswith('_')]
        display_df = df[display_columns]

        st.markdown("**Click on a row to view rep details**")

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

        # Configure column widths
        gb.configure_column("Rep", width=150)
        gb.configure_column("Segment", width=120)
        gb.configure_column("Calls", width=100)
        gb.configure_column("Accounts", width=120)
        gb.configure_column("Discovery Avg", width=130)
        gb.configure_column("Trial Avg", width=120)
        gb.configure_column("Negotiation Avg", width=150)
        gb.configure_column("Active Deals", width=130)

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

        st.markdown(f"**Showing {len(table_data)} rep(s)**")

        # Handle row selection with AG Grid
        selected_rows = grid_response['selected_rows']
        if selected_rows is not None and len(selected_rows) > 0:
            # selected_rows is a DataFrame, use iloc to get first row
            selected_row = selected_rows.iloc[0]
            # Need to find the email from the original table_data using the Rep name
            selected_rep_name = selected_row['Rep']
            selected_rep_email = next((r['_email'] for r in table_data if r['Rep'] == selected_rep_name), None)
            if selected_rep_email:
                st.session_state['selected_rep_email'] = selected_rep_email

        # Show selected rep details from session state
        if 'selected_rep_email' in st.session_state:
            st.markdown("---")
            show_rep_detail(st.session_state['selected_rep_email'], repo, date_from, date_to)

    finally:
        db.close()


if __name__ == "__main__":
    main()
