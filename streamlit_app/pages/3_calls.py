"""Calls Dashboard - Analyze individual calls across the pipeline."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

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

from src.core import Config, LLMClient, GongClient
from src.data import Database, Repository

# Page config
st.set_page_config(
    page_title="Calls - Introspect",
    page_icon="📞",
    layout="wide"
)


# ============================================================================
# Constants & Helpers
# ============================================================================

STAGE_COLORS = {
    "discovery": "#3498db",    # Blue
    "trial": "#f39c12",        # Orange
    "negotiation": "#9b59b6",  # Purple
    "closed": "#2ecc71"        # Green
}

STAGE_EMOJIS = {
    "discovery": "🔍",
    "trial": "🧪",
    "negotiation": "💼",
    "closed": "✅"
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
# Data Loading
# ============================================================================

def get_call_transcript(repo: Repository, gong_client: GongClient, call_id: str) -> Optional[str]:
    """
    Fetch and enrich transcript for a call.

    Fetches from Gong API and enriches with participant names/roles.
    Format: [Sales - John]: text or [Customer - Sarah]: text
    """
    try:
        # Fetch raw transcript from Gong
        transcripts = gong_client.get_transcripts([call_id])
        raw_transcript = transcripts.get(call_id)

        if not raw_transcript:
            return None

        # Enrich with participant info (replaces speaker IDs with names/roles)
        enriched_transcript = repo.enrich_transcript_with_participants(call_id, raw_transcript)

        return enriched_transcript

    except Exception as e:
        print(f"Error fetching transcript for {call_id}: {e}")
        return None


def build_analysis_context(repo: Repository, gong_client: GongClient, call_ids: List[str]) -> str:
    """Build LLM context from selected calls."""
    context_parts = []

    context_parts.append(f"You are analyzing {len(call_ids)} sales call(s).\n")
    context_parts.append("=" * 80)
    context_parts.append("\n\n")

    for i, call_id in enumerate(call_ids, 1):
        # Get call metadata
        cursor = repo.conn.execute("""
            SELECT c.call_id, c.call_title, c.call_date, c.primary_stage,
                   c.sales_rep_email, a.domain as account_domain
            FROM calls c
            JOIN accounts a ON c.account_id = a.id
            WHERE c.call_id = ?
        """, (call_id,))

        call_row = cursor.fetchone()
        if not call_row:
            continue

        context_parts.append(f"CALL {i}: {call_row['account_domain']} - {call_row['call_title']}")
        context_parts.append(f"Date: {call_row['call_date']}")
        context_parts.append(f"Stage: {call_row['primary_stage'].title()}")
        context_parts.append(f"Sales Rep: {call_row['sales_rep_email']}")

        # Get participants
        participants = repo.get_call_participants(call_id)
        if participants:
            external = [p for p in participants.values() if p.get('affiliation') == 'External']
            if external:
                context_parts.append("Customer Participants:")
                for p in external[:5]:  # Limit to 5
                    name = p.get('name', 'Unknown')
                    title = p.get('title', '')
                    persona = p.get('persona', '')
                    context_parts.append(f"  - {name}" + (f" ({title})" if title else "") + (f" [{persona}]" if persona else ""))

        # Get scores if available
        stage = call_row['primary_stage']
        if stage == 'discovery':
            scores = repo.get_call_meddpicc_scores(call_id)
            if scores:
                context_parts.append(f"MEDDPICC Score: {scores.scores.overall_score:.1f}/5.0")
        elif stage == 'trial':
            scores = repo.get_call_trial_scores(call_id)
            if scores:
                context_parts.append(f"Trial Health: {scores.scores.overall_score:.1f}/5.0 ({scores.scores.health_interpretation or 'unknown'})")
        elif stage == 'negotiation':
            scores = repo.get_call_close_scores(call_id)
            if scores:
                context_parts.append(f"Close Health: {scores.scores.overall_score:.1f}/5.0 ({scores.scores.health_interpretation or 'unknown'})")

        # Get transcript (fetched from Gong and enriched with participant info)
        transcript = get_call_transcript(repo, gong_client, call_id)
        if transcript:
            context_parts.append("\nTranscript (speaker format: [Role - Name]):")
            context_parts.append(transcript[:20000])  # Limit transcript size per call
            if len(transcript) > 20000:
                context_parts.append("\n[... transcript truncated ...]")
        else:
            context_parts.append("\n[No transcript available]")

        context_parts.append("\n" + "-" * 80 + "\n\n")

    return "\n".join(context_parts)


def analyze_calls_with_llm(llm_client: LLMClient, context: str, user_prompt: str) -> str:
    """Send calls context and user prompt to LLM."""
    full_prompt = f"""{context}

USER QUESTION:
{user_prompt}

Please analyze the call(s) above and provide a comprehensive answer to the question."""

    try:
        response = llm_client.call_llm(full_prompt, max_tokens=4000)
        return response
    except Exception as e:
        return f"Error analyzing calls: {str(e)}"


def load_calls(repo: Repository, stage: Optional[str] = None, segment: Optional[str] = None,
               date_from: Optional[datetime] = None, date_to: Optional[datetime] = None) -> List:
    """Load calls from database with filtering."""
    # Build query with filters
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

    query_parts.append("ORDER BY call_date DESC")
    query = " ".join(query_parts)

    cursor = repo.conn.execute(query, params)
    rows = cursor.fetchall()

    calls = []
    for row in rows:
        call = repo._row_to_call(row)

        # Load account to get segment
        account_obj = repo.get_account(call.account_id)
        if account_obj:
            call.account_domain = account_obj.domain
            call.account_segment = account_obj.primary_segment

            # Filter by segment if specified
            if segment and segment != "All":
                if account_obj.primary_segment != segment.lower():
                    continue

        # Load stage-specific scores
        stage = call.primary_stage
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

def build_calls_scatter_chart(calls: List) -> go.Figure:
    """Build scatter plot of call scores over time, colored by stage."""
    # Group calls by stage
    stages_data = {
        "discovery": [],
        "trial": [],
        "negotiation": [],
        "closed": []
    }

    for call in calls:
        stage = call.primary_stage
        if stage not in stages_data:
            continue

        # Get score based on stage
        score = None
        if stage == "discovery" and hasattr(call, 'meddpicc_scores'):
            score = call.meddpicc_scores.overall_score
        elif stage == "trial" and hasattr(call, 'trial_scores'):
            score = call.trial_scores.overall_score
        elif stage == "negotiation" and hasattr(call, 'close_scores'):
            score = call.close_scores.overall_score
        # Note: closed deals don't have a 0-5 score, so we skip them

        if score is not None:
            stages_data[stage].append({
                "date": call.call_date,
                "score": score,
                "account": getattr(call, 'account_domain', 'Unknown'),
                "rep": call.sales_rep_email.split("@")[0] if "@" in call.sales_rep_email else call.sales_rep_email,
                "title": call.call_title[:50]
            })

    # Create figure
    fig = go.Figure()

    # Add trace for each stage
    for stage, data in stages_data.items():
        if not data:
            continue

        fig.add_trace(go.Scatter(
            x=[d["date"] for d in data],
            y=[d["score"] for d in data],
            mode='markers',
            name=stage.title(),
            marker=dict(
                size=10,
                color=STAGE_COLORS[stage],
                opacity=0.7,
                line=dict(color='white', width=1)
            ),
            text=[f"{d['account']}<br>{d['title']}" for d in data],
            hovertemplate=(
                '<b>%{text}</b><br>'
                'Date: %{x|%b %d, %Y}<br>'
                'Score: %{y:.1f}/5<br>'
                '<extra></extra>'
            )
        ))

    fig.update_layout(
        title="Call Quality Scores Over Time",
        xaxis_title="Call Date",
        yaxis_title="Score (0-5)",
        yaxis_range=[0, 5.5],
        height=500,
        hovermode='closest',
        showlegend=True
    )

    return fig


# ============================================================================
# Table Building
# ============================================================================

def build_calls_table(calls: List) -> List[Dict]:
    """Build table data for calls."""
    table_data = []

    for i, call in enumerate(calls, 1):
        stage = call.primary_stage
        stage_emoji = STAGE_EMOJIS.get(stage, "📊")

        # Get score based on stage
        score = None
        status = "N/A"

        if stage == "discovery" and hasattr(call, 'meddpicc_scores'):
            score = call.meddpicc_scores.overall_score
            if score >= 4.0:
                status = f"{get_score_emoji(score)} Strong"
            elif score >= 2.5:
                status = f"{get_score_emoji(score)} Moderate"
            else:
                status = f"{get_score_emoji(score)} Weak"

        elif stage == "trial" and hasattr(call, 'trial_scores'):
            score = call.trial_scores.overall_score
            health = call.trial_scores.health_interpretation or "unknown"
            status = f"{HEALTH_EMOJIS.get(health, '⚪')} {health.title()}"

        elif stage == "negotiation" and hasattr(call, 'close_scores'):
            score = call.close_scores.overall_score
            health = call.close_scores.health_interpretation or "unknown"
            status = f"{HEALTH_EMOJIS.get(health, '⚪')} {health.title()}"

        elif stage == "closed" and hasattr(call, 'winloss_analysis'):
            outcome = call.winloss_analysis.outcome
            status = f"{OUTCOME_EMOJIS.get(outcome, '⚪')} {outcome.title()}"

        # Format sales rep
        sales_rep = call.sales_rep_email
        if "@" in sales_rep:
            sales_rep = sales_rep.split("@")[0]

        # Format account domain
        account = getattr(call, 'account_domain', 'Unknown')
        segment = getattr(call, 'account_segment', 'unknown')

        gong_link = format_gong_link(call.call_id)

        row = {
            "Call Date": format_date(call.call_date),
            "Account": account,
            "Sales Rep": sales_rep,
            "Segment": segment.title() if segment else "Unknown",
            "Stage": f"{stage_emoji} {stage.title()}",
            "Score": f"{score:.1f}" if score is not None else "N/A",
            "Call Title": call.call_title,
            "gong_link": gong_link,  # Keep as regular column, will hide in grid
            "_call_id": call.call_id,
            "_call_date": call.call_date
        }

        table_data.append(row)

    return table_data


# ============================================================================
# Call Detail View
# ============================================================================

def show_call_detail(call, repo: Repository):
    """Show detailed call information."""
    stage = call.primary_stage
    stage_emoji = STAGE_EMOJIS.get(stage, "📊")

    # Header
    st.markdown(f"## {stage_emoji} {call.call_title}")
    st.markdown(f"**Account:** {getattr(call, 'account_domain', 'Unknown')}")
    st.markdown(f"**Date:** {format_date(call.call_date)}")
    st.markdown(f"**Sales Rep:** {call.sales_rep_email}")
    st.markdown(f"**Stage:** {stage.title()}")

    # Show call participants
    participants = repo.get_call_participants(call.call_id)
    if participants:
        external_participants = [p for p in participants.values() if p.get('affiliation') == 'External']
        internal_participants = [p for p in participants.values() if p.get('affiliation') == 'Internal']

        st.markdown(f"**Participants:** {len(internal_participants)} Internal, {len(external_participants)} External")

        # Show participants in expandable section
        with st.expander(f"👥 Call Attendees ({len(participants)} total)", expanded=False):
            if internal_participants:
                st.markdown("**Internal:**")
                for p in internal_participants:
                    name = p.get('name', 'Unknown')
                    email = p.get('email_address', '')
                    st.markdown(f"• {name} ({email})")

            if external_participants:
                st.markdown("**Customer:**")
                for p in external_participants:
                    name = p.get('name', 'Unknown')
                    title = p.get('title', '')
                    email = p.get('email_address', '')
                    st.markdown(f"• **{name}** {f'({title})' if title else ''}")
                    if email:
                        st.markdown(f"  _{email}_")

    st.markdown("---")

    # Stage-specific details
    if stage == "discovery" and hasattr(call, 'meddpicc_scores'):
        scores = call.meddpicc_scores

        # Overall score
        st.metric("MEDDPICC Score", f"{scores.overall_score:.1f}/5.0")

        # Dimension breakdown
        st.markdown("**Dimension Scores:**")
        cols = st.columns(4)
        dimensions = [
            ("M", scores.metrics),
            ("E", scores.economic_buyer),
            ("DD", scores.decision_criteria),
            ("DP", scores.decision_process),
            ("P", scores.paper_process),
            ("I", scores.identify_pain),
            ("C", scores.champion),
            ("C", scores.competition)
        ]
        for i, (label, score) in enumerate(dimensions):
            cols[i % 4].metric(label, f"{score}/5")

        # Full text fields
        if scores.meddpicc_summary:
            st.markdown("**Summary:**")
            st.markdown(f"> {scores.meddpicc_summary}")

        if scores.key_gaps:
            st.markdown("**Key Gaps:**")
            st.markdown(f"> {scores.key_gaps}")

        if scores.clarity_of_need:
            st.markdown("**Clarity of Need:**")
            st.markdown(f"> {scores.clarity_of_need}")

        if scores.key_influencers:
            st.markdown("**Key Influencers:**")
            st.markdown(f"> {scores.key_influencers}")

        if scores.next_steps:
            st.markdown("**Next Steps:**")
            st.markdown(f"> {scores.next_steps}")

        if scores.trial_readiness:
            st.markdown("**Trial Readiness:**")
            st.markdown(f"> {scores.trial_readiness}")

    elif stage == "trial" and hasattr(call, 'trial_scores'):
        scores = call.trial_scores

        # Overall score
        health_emoji = HEALTH_EMOJIS.get(scores.health_interpretation or "unknown", "⚪")
        st.metric("Trial Health Score", f"{scores.overall_score:.1f}/5.0")
        st.markdown(f"**Health:** {health_emoji} {(scores.health_interpretation or 'unknown').title()}")
        st.markdown(f"**Likelihood to Advance:** {(scores.likelihood_to_advance or 'unknown').title()}")

        # Dimension breakdown
        st.markdown("**Dimension Scores:**")
        cols = st.columns(5)
        cols[0].metric("T", f"{scores.technical_validation}/5")
        cols[1].metric("R", f"{scores.readiness_progress}/5")
        cols[2].metric("I", f"{scores.internal_adoption}/5")
        cols[3].metric("A", f"{scores.advocacy_sentiment}/5")
        cols[4].metric("L", f"{scores.landscape_competition}/5")

        # Full text fields
        if scores.primary_concern_category:
            st.markdown(f"**Primary Concern:** {scores.primary_concern_category.title()}")

        if scores.concern_severity:
            st.markdown(f"**Concern Severity:** {scores.concern_severity.title()}")

        if scores.is_bake_off:
            st.warning("⚠️ **This is a competitive bake-off**")

        if scores.key_concerns:
            st.markdown("**Key Concerns:**")
            st.markdown(f"> {scores.key_concerns}")

        if scores.recommended_actions:
            st.markdown("**Recommended Actions:**")
            st.markdown(f"> {scores.recommended_actions}")

        if scores.next_steps:
            st.markdown("**Next Steps:**")
            st.markdown(f"> {scores.next_steps}")

    elif stage == "negotiation" and hasattr(call, 'close_scores'):
        scores = call.close_scores

        # Overall score
        health_emoji = HEALTH_EMOJIS.get(scores.health_interpretation or "unknown", "⚪")
        st.metric("Deal Health Score", f"{scores.overall_score:.1f}/5.0")
        st.markdown(f"**Health:** {health_emoji} {(scores.health_interpretation or 'unknown').title()}")
        st.markdown(f"**Likelihood to Close:** {(scores.likelihood_to_close or 'unknown').title()}")

        # Dimension breakdown
        st.markdown("**Dimension Scores:**")
        cols = st.columns(5)
        cols[0].metric("C", f"{scores.commercial_alignment}/5")
        cols[1].metric("L", f"{scores.legal_compliance}/5")
        cols[2].metric("O", f"{scores.organizational_consensus}/5")
        cols[3].metric("S", f"{scores.single_threading_risk}/5")
        cols[4].metric("E", f"{scores.execution_momentum}/5")

        # Full text fields
        if scores.primary_concern_category:
            st.markdown(f"**Primary Concern:** {scores.primary_concern_category.title()}")

        if scores.concern_severity:
            st.markdown(f"**Concern Severity:** {scores.concern_severity.title()}")

        if scores.has_competitive_pressure:
            st.warning("⚠️ **Competitive pressure present**")

        if scores.key_concerns:
            st.markdown("**Key Concerns:**")
            st.markdown(f"> {scores.key_concerns}")

        if scores.recommended_actions:
            st.markdown("**Recommended Actions:**")
            st.markdown(f"> {scores.recommended_actions}")

        if scores.next_steps:
            st.markdown("**Next Steps:**")
            st.markdown(f"> {scores.next_steps}")

    elif stage == "closed" and hasattr(call, 'winloss_analysis'):
        analysis = call.winloss_analysis

        outcome_emoji = OUTCOME_EMOJIS.get(analysis.outcome, "⚪")
        st.markdown(f"### {outcome_emoji} Deal {analysis.outcome.title()}")

        if analysis.stage_of_decision:
            st.markdown(f"**Stage of Decision:** {analysis.stage_of_decision.title()}")

        if analysis.primary_reasons:
            st.markdown("**Primary Reasons:**")
            st.markdown(f"> {analysis.primary_reasons}")

        if analysis.critical_dimensions:
            st.markdown("**Critical Dimensions:**")
            st.markdown(f"> {analysis.critical_dimensions}")

        if analysis.competitive_factor:
            st.markdown("**Competitive Factor:**")
            st.markdown(f"> {analysis.competitive_factor}")

        if analysis.key_learnings:
            st.markdown("**Key Learnings:**")
            st.markdown(f"> {analysis.key_learnings}")

        if analysis.verbatim_quotes:
            st.markdown("**Verbatim Quotes:**")
            st.markdown(f"> {analysis.verbatim_quotes}")


# ============================================================================
# Main App
# ============================================================================

def main():
    """Main calls dashboard."""

    # Load Font Awesome
    st.markdown("""
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    """, unsafe_allow_html=True)

    st.markdown('<h1 style="margin-bottom: 0;"><i class="fas fa-phone" style="color: #3498db;"></i> Calls Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color: #7f8c8d; margin-top: 0; margin-bottom: 1rem;">Analyze individual calls across the pipeline</p>', unsafe_allow_html=True)
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
            index=1  # Default to last 30 days
        )

        days = date_options[date_selection]
        date_from = datetime.now() - timedelta(days=days) if days else None
        date_to = None

        # Stage filter
        stage_selection = st.sidebar.selectbox(
            "Stage",
            options=["All", "Discovery", "Trial", "Negotiation", "Closed"],
            index=0
        )

        # Segment filter
        segment_options = ["All"] + [seg.title() for seg in segments]
        segment_selection = st.sidebar.selectbox(
            "Segment",
            options=segment_options,
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
        with st.spinner("Loading calls..."):
            calls = load_calls(
                repo,
                stage=stage_selection if stage_selection != "All" else None,
                segment=segment_selection.lower() if segment_selection != "All" else None,
                date_from=date_from,
                date_to=date_to
            )

        if not calls:
            st.warning("No calls found with the selected filters.")
            return

        # Summary metrics
        # Calculate calls by stage with scores
        discovery_calls = [c for c in calls if c.primary_stage == "discovery" and hasattr(c, 'meddpicc_scores')]
        trial_calls = [c for c in calls if c.primary_stage == "trial" and hasattr(c, 'trial_scores')]
        negotiation_calls = [c for c in calls if c.primary_stage == "negotiation" and hasattr(c, 'close_scores')]
        closed_calls = [c for c in calls if c.primary_stage == "closed"]

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(f"""
                <div style="text-align: center; padding: 5px;">
                    <p style="color: #7f8c8d; font-size: 0.85rem; margin: 0 0 3px 0;">
                        <i class="fas fa-phone" style="color: #3498db;"></i> Total Calls
                    </p>
                    <p style="font-size: 1.8rem; font-weight: bold; margin: 0; line-height: 1;">{len(calls)}</p>
                </div>
            """, unsafe_allow_html=True)

        with col2:
            discovery_count = len([c for c in calls if c.primary_stage == "discovery"])
            if discovery_calls:
                avg_discovery = sum(c.meddpicc_scores.overall_score for c in discovery_calls) / len(discovery_calls)
                st.markdown(f"""
                    <div style="text-align: center; padding: 5px;">
                        <p style="color: #7f8c8d; font-size: 0.85rem; margin: 0 0 3px 0;">
                            <i class="fas fa-search" style="color: #3498db;"></i> Discovery
                        </p>
                        <p style="font-size: 1.8rem; font-weight: bold; margin: 0; line-height: 1;">{discovery_count}</p>
                        <p style="font-size: 0.85rem; color: #7f8c8d; margin: 0;">Avg: {avg_discovery:.1f}</p>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div style="text-align: center; padding: 5px;">
                        <p style="color: #7f8c8d; font-size: 0.85rem; margin: 0 0 3px 0;">
                            <i class="fas fa-search" style="color: #3498db;"></i> Discovery
                        </p>
                        <p style="font-size: 1.8rem; font-weight: bold; margin: 0; line-height: 1;">{discovery_count}</p>
                    </div>
                """, unsafe_allow_html=True)

        with col3:
            trial_count = len([c for c in calls if c.primary_stage == "trial"])
            if trial_calls:
                avg_trial = sum(c.trial_scores.overall_score for c in trial_calls) / len(trial_calls)
                st.markdown(f"""
                    <div style="text-align: center; padding: 5px;">
                        <p style="color: #7f8c8d; font-size: 0.85rem; margin: 0 0 3px 0;">
                            <i class="fas fa-flask" style="color: #9b59b6;"></i> Trial
                        </p>
                        <p style="font-size: 1.8rem; font-weight: bold; margin: 0; line-height: 1;">{trial_count}</p>
                        <p style="font-size: 0.85rem; color: #7f8c8d; margin: 0;">Avg: {avg_trial:.1f}</p>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div style="text-align: center; padding: 5px;">
                        <p style="color: #7f8c8d; font-size: 0.85rem; margin: 0 0 3px 0;">
                            <i class="fas fa-flask" style="color: #9b59b6;"></i> Trial
                        </p>
                        <p style="font-size: 1.8rem; font-weight: bold; margin: 0; line-height: 1;">{trial_count}</p>
                    </div>
                """, unsafe_allow_html=True)

        with col4:
            negotiation_count = len([c for c in calls if c.primary_stage == "negotiation"])
            if negotiation_calls:
                avg_negotiation = sum(c.close_scores.overall_score for c in negotiation_calls) / len(negotiation_calls)
                st.markdown(f"""
                    <div style="text-align: center; padding: 5px;">
                        <p style="color: #7f8c8d; font-size: 0.85rem; margin: 0 0 3px 0;">
                            <i class="fas fa-handshake" style="color: #27ae60;"></i> Negotiation
                        </p>
                        <p style="font-size: 1.8rem; font-weight: bold; margin: 0; line-height: 1;">{negotiation_count}</p>
                        <p style="font-size: 0.85rem; color: #7f8c8d; margin: 0;">Avg: {avg_negotiation:.1f}</p>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div style="text-align: center; padding: 5px;">
                        <p style="color: #7f8c8d; font-size: 0.85rem; margin: 0 0 3px 0;">
                            <i class="fas fa-handshake" style="color: #27ae60;"></i> Negotiation
                        </p>
                        <p style="font-size: 1.8rem; font-weight: bold; margin: 0; line-height: 1;">{negotiation_count}</p>
                    </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        # Scatter plot chart
        scatter_chart = build_calls_scatter_chart(calls)
        st.plotly_chart(scatter_chart, use_container_width=True)

        # Calls table
        st.markdown('<h3><i class="fas fa-table" style="color: #3498db;"></i> Call Details</h3>', unsafe_allow_html=True)
        table_data = build_calls_table(calls)

        if not table_data:
            st.info("No call data available.")
            return

        # Display table with AG Grid (has built-in column filters)
        df = pd.DataFrame(table_data)
        display_columns = [col for col in df.columns if not col.startswith('_')]
        display_df = df[display_columns]

        st.markdown("**Select calls for analysis** • Click column headers to filter/sort • Hold Ctrl/Cmd to select multiple rows")

        # Configure AG Grid
        gb = GridOptionsBuilder.from_dataframe(display_df)
        gb.configure_default_column(
            filterable=True,
            sortable=True,
            resizable=True,
            filter=True
        )
        gb.configure_selection(
            selection_mode='multiple',
            use_checkbox=True,
            header_checkbox=True
        )

        # Hide gong_link column (used for rendering)
        gb.configure_column("gong_link", hide=True)

        # Configure column widths
        gb.configure_column("Call Date", width=120)
        gb.configure_column("Account", width=150)
        gb.configure_column("Sales Rep", width=120)
        gb.configure_column("Segment", width=100)
        gb.configure_column("Stage", width=120)
        gb.configure_column("Score", width=80)

        # Make Call Title clickable - style it like a link and handle clicks
        gb.configure_column(
            "Call Title",
            flex=1,
            minWidth=400,
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

        selected_rows = grid_response['selected_rows']
        if selected_rows is not None and len(selected_rows) > 0:
            selected_df = pd.DataFrame(selected_rows)
        else:
            selected_df = pd.DataFrame()

        st.markdown(f"**Selected: {len(selected_df)} call(s)**")

        # ============================================================================
        # Ad-hoc Analysis Section
        # ============================================================================

        if len(selected_df) > 0:
            st.markdown("---")
            st.markdown('<h3><i class="fas fa-search" style="color: #2ecc71;"></i> Ad-hoc Call Analysis</h3>', unsafe_allow_html=True)

            # Get call IDs from selected rows
            # Match selected rows back to original table_data to get _call_id
            selected_call_ids = []
            for _, selected_row in selected_df.iterrows():
                # Find matching row in original table_data
                for row in table_data:
                    if (row['Account'] == selected_row['Account'] and
                        row['Call Date'] == selected_row['Call Date'] and
                        row['Call Title'] == selected_row['Call Title']):
                        selected_call_ids.append(row['_call_id'])
                        break

            # Show selected calls summary
            with st.expander(f"📋 Selected Calls ({len(selected_call_ids)})", expanded=False):
                for _, row in selected_df.iterrows():
                    st.markdown(f"- **{row['Account']}** - {row['Call Title'][:50]} ({row['Call Date']})")

            # Analysis prompt input
            col1, col2 = st.columns([3, 1])

            with col1:
                user_prompt = st.text_area(
                    "Ask a question about the selected calls:",
                    placeholder="Example: What are the main objections mentioned across these calls?",
                    height=100,
                    key="analysis_prompt"
                )

            with col2:
                st.markdown("")  # Spacing
                st.markdown("")  # Spacing
                analyze_button = st.button(
                    f"🔍 Analyze {len(selected_call_ids)} Call(s)",
                    type="primary",
                    use_container_width=True
                )

            # Perform analysis
            if analyze_button and user_prompt.strip():
                # Initialize clients
                try:
                    llm_client = LLMClient(
                        anthropic_api_key=config.LLM_API_KEY,
                        model=config.LLM_MODEL
                    )

                    gong_client = GongClient(
                        access_key=config.GONG_ACCESS_KEY,
                        secret_key=config.GONG_SECRET_KEY,
                        api_url=config.GONG_API_URL,
                        internal_domain=config.INTERNAL_DOMAIN,
                    )

                    with st.spinner(f"🤖 Fetching transcripts and analyzing {len(selected_call_ids)} call(s)... This may take 60-90 seconds."):
                        # Build context (fetches transcripts from Gong and enriches)
                        context = build_analysis_context(repo, gong_client, selected_call_ids)

                        # Call LLM
                        response = analyze_calls_with_llm(llm_client, context, user_prompt)

                    # Display results
                    st.markdown("#### 📊 Analysis Results")
                    st.markdown(f"**Your Question:** {user_prompt}")
                    st.markdown("---")
                    st.markdown(response)

                    # Show token estimate
                    estimated_tokens = len(context.split()) + len(user_prompt.split()) + len(response.split())
                    st.caption(f"_Estimated tokens used: ~{estimated_tokens:,}_")

                except Exception as e:
                    st.error(f"Error during analysis: {str(e)}")
                    import traceback
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())

            elif analyze_button and not user_prompt.strip():
                st.warning("Please enter a question before analyzing.")

            st.markdown("---")

        # Handle single row selection - show detail view
        if len(selected_df) == 1:
            selected_row = selected_df.iloc[0]

            # Find matching call_id from original table_data
            selected_call_id = None
            for row in table_data:
                if (row['Account'] == selected_row['Account'] and
                    row['Call Date'] == selected_row['Call Date'] and
                    row['Call Title'] == selected_row['Call Title']):
                    selected_call_id = row['_call_id']
                    break

            if selected_call_id:
                # Find the call object
                selected_call = next(
                    (c for c in calls if c.call_id == selected_call_id),
                    None
                )

                if selected_call:
                    st.markdown("---")
                    st.markdown("### 📄 Call Details")
                    show_call_detail(selected_call, repo)

    finally:
        db.close()


if __name__ == "__main__":
    main()
