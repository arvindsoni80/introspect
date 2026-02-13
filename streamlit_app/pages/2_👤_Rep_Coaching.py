"""Rep Coaching Dashboard - Individual rep performance and coaching."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config import load_settings
from src.sqlite_repository import SQLiteCallRepository
from streamlit_app.utils import db_queries, metrics, styling, pagination

# Page config
st.set_page_config(
    page_title="Rep Coaching - Introspect",
    page_icon="👤",
    layout="wide"
)


async def load_data(date_from=None, date_to=None):
    """Load accounts from database with optional date filtering."""
    settings = load_settings()
    repo = SQLiteCallRepository(settings.sqlite_db_path)

    try:
        accounts = await db_queries.get_all_accounts_filtered(
            repo,
            date_from=date_from,
            date_to=date_to
        )
        return accounts
    finally:
        await repo.close()


def build_comparison_chart(rep_scores, team_scores, rep_email):
    """Build rep vs team comparison chart with consistent MEDDPICC order."""
    dimensions = styling.MEDDPICC_DIMENSIONS
    dim_labels = [styling.format_dimension_name(d) for d in dimensions]

    rep_values = [rep_scores.get(d, 0) for d in dimensions]
    team_values = [team_scores.get(d, 0) for d in dimensions]

    # Keep MEDDPICC order consistent (M, E, DC, DP, PP, IP, CH, CO)
    # Reverse for display (bottom to top)
    dim_labels_reversed = list(reversed(dim_labels))
    rep_values_reversed = list(reversed(rep_values))
    team_values_reversed = list(reversed(team_values))

    # Create figure
    fig = go.Figure()

    # Rep scores
    colors = [styling.get_score_color(v) for v in rep_values_reversed]
    fig.add_trace(go.Bar(
        y=dim_labels_reversed,
        x=rep_values_reversed,
        name=rep_email.split('@')[0],
        orientation='h',
        marker=dict(color=colors),
        text=[f"{v:.1f}" for v in rep_values_reversed],
        textposition='inside',
        hovertemplate='<b>%{y}</b><br>Rep Score: %{x:.1f}<extra></extra>'
    ))

    # Team average line
    fig.add_trace(go.Scatter(
        y=dim_labels_reversed,
        x=team_values_reversed,
        mode='markers',
        name='Team Avg',
        marker=dict(
            symbol='line-ns',
            size=15,
            color='black',
            line=dict(width=3)
        ),
        hovertemplate='<b>%{y}</b><br>Team Avg: %{x:.1f}<extra></extra>'
    ))

    fig.update_layout(
        title=f"Rep vs Team Comparison (MEDDPICC Order)",
        xaxis_title="Score",
        xaxis_range=[0, 5],
        height=400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig


def build_progress_chart(rep_calls):
    """Build progress chart showing rep's scores over time."""
    if not rep_calls or len(rep_calls) < 2:
        return None

    # Sort by date
    sorted_calls = sorted(rep_calls, key=lambda c: c.call_date)

    dates = [c.call_date for c in sorted_calls]
    overall_scores = [c.meddpicc_scores.overall_score for c in sorted_calls]

    # Create figure
    fig = go.Figure()

    # Overall score line
    fig.add_trace(go.Scatter(
        x=dates,
        y=overall_scores,
        mode='lines+markers',
        name='Overall Score',
        line=dict(color=styling.COLORS['info'], width=3),
        marker=dict(size=10),
        hovertemplate='<b>%{x|%b %d, %Y}</b><br>Score: %{y:.1f}<extra></extra>'
    ))

    fig.update_layout(
        title="Progress Over Time",
        xaxis_title="Date",
        yaxis_title="Score",
        yaxis_range=[0, 5],
        height=350,
        hovermode='x unified'
    )

    return fig


def main():
    """Main rep coaching dashboard."""

    st.title("👤 Individual Rep Coaching Dashboard")

    # Sidebar: Date filter and rep selector
    st.sidebar.header("Filters")

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

    # Calculate date range
    days = date_options[date_selection]
    date_from = datetime.now() - timedelta(days=days) if days else None
    date_to = None

    # Load data
    with st.spinner("Loading data..."):
        accounts = asyncio.run(load_data(date_from, date_to))

    if not accounts:
        st.warning("No discovery calls found for the selected date range.")
        return

    # Get all reps
    all_reps = db_queries.get_all_reps(accounts)

    if not all_reps:
        st.warning("No sales reps found.")
        return

    # Rep selector
    selected_rep = st.sidebar.selectbox(
        "Select Sales Rep",
        options=all_reps,
        format_func=lambda x: x.split('@')[0]  # Show just username
    )

    st.sidebar.markdown("---")
    st.sidebar.info(f"Analyzing {len(all_reps)} reps across {len(accounts)} accounts")

    # Get data for selected rep
    rep_calls = db_queries.get_calls_by_rep(accounts, selected_rep)

    if not rep_calls:
        st.warning(f"No discovery calls found for {selected_rep}")
        return

    # Get team stats for comparison
    team_stats = db_queries.get_team_stats(accounts)
    rep_comparison = db_queries.get_rep_comparison(accounts)

    # Find this rep's stats
    rep_stats = next((r for r in rep_comparison if r['rep_email'] == selected_rep), None)

    if not rep_stats:
        st.error("Could not find rep stats")
        return

    # Header
    st.markdown("---")

    # Rep summary card
    rep_score = rep_stats['avg_overall_score']
    team_score = team_stats['avg_overall_score']
    delta = rep_score - team_score

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="📊 Discovery Calls",
            value=rep_stats['total_calls']
        )

    with col2:
        emoji = styling.get_score_emoji(rep_score)
        st.metric(
            label="🎯 Rep Score",
            value=f"{emoji} {styling.format_score(rep_score)}"
        )

    with col3:
        team_emoji = styling.get_score_emoji(team_score)
        st.metric(
            label="👥 Team Average",
            value=f"{team_emoji} {styling.format_score(team_score)}"
        )

    with col4:
        delta_emoji = "📈" if delta > 0 else "📉" if delta < 0 else "→"
        delta_color = "normal" if abs(delta) < 0.2 else ("inverse" if delta > 0 else "off")
        st.metric(
            label="vs Team",
            value=f"{delta_emoji} {styling.format_delta(delta)}",
            delta=None
        )

    st.markdown("---")

    # Rep vs Team Comparison Chart
    st.subheader("📊 Your MEDDPICC Scorecard")
    st.markdown("Compare your performance against team averages. Bars sorted by biggest gaps.")

    comparison_chart = build_comparison_chart(
        rep_stats['avg_scores_by_dimension'],
        team_stats['avg_scores_by_dimension'],
        selected_rep
    )
    st.plotly_chart(comparison_chart, use_container_width=True)

    st.markdown("---")

    # Top 3 Focus Areas
    st.subheader("🎯 Your Top 3 Focus Areas")

    strengths, weaknesses = metrics.get_rep_strengths_and_weaknesses(
        rep_stats['avg_scores_by_dimension'],
        team_stats['avg_scores_by_dimension'],
        top_n=3
    )

    for i, weakness in enumerate(weaknesses, 1):
        severity_emoji = "🔴" if weakness['rep_score'] < 2.5 else "🟡"

        with st.expander(
            f"{severity_emoji} **{i}. {weakness['dimension_name']}** "
            f"(Your score: {styling.format_score(weakness['rep_score'])}, "
            f"Team: {styling.format_score(weakness['team_score'])})",
            expanded=(i == 1)
        ):
            # Show what they're missing
            dim_key = weakness['dimension']

            if weakness['rep_score'] < 3.0:
                st.markdown("**What you're missing:**")

                if dim_key == 'economic_buyer':
                    st.markdown("- Engaging with C-level or budget authority")
                    st.markdown("- Confirming who controls the budget")
                    st.markdown("- Getting economic buyer on calls")
                elif dim_key == 'paper_process':
                    st.markdown("- Legal review process and timeline")
                    st.markdown("- Procurement requirements")
                    st.markdown("- Signature authority")
                elif dim_key == 'champion':
                    st.markdown("- Testing champion's power and influence")
                    st.markdown("- Confirming willingness to sell internally")
                    st.markdown("- Getting champion to multi-thread")
                elif dim_key == 'competition':
                    st.markdown("- Detailed competitive landscape")
                    st.markdown("- Evaluation criteria and scoring")
                    st.markdown("- What they like/dislike about alternatives")
                elif dim_key == 'metrics':
                    st.markdown("- Quantifiable success metrics")
                    st.markdown("- ROI targets or financial impact")
                    st.markdown("- Measurable outcomes")

                st.markdown("**Questions to ask:**")

                if dim_key == 'economic_buyer':
                    st.markdown('- "Who ultimately controls the budget for this?"')
                    st.markdown('- "Can we get the CFO/economic buyer on our next call?"')
                elif dim_key == 'paper_process':
                    st.markdown('- "Walk me through what happens after we agree on terms"')
                    st.markdown('- "Who needs to sign off internally?"')
                    st.markdown('- "What\'s your typical procurement timeline?"')
                elif dim_key == 'champion':
                    st.markdown('- "Are you willing to advocate for us internally?"')
                    st.markdown('- "Who else should we be talking to?"')
                    st.markdown('- "How much influence do you have with the decision makers?"')
                elif dim_key == 'competition':
                    st.markdown('- "Who else are you evaluating?"')
                    st.markdown('- "What do you like/dislike about [competitor]?"')
                    st.markdown('- "What criteria matter most in your evaluation?"')
                elif dim_key == 'metrics':
                    st.markdown('- "What metrics will you use to measure success?"')
                    st.markdown('- "What\'s the financial impact if this isn\'t solved?"')
                    st.markdown('- "What ROI are you targeting?"')

            # Best example call
            best_call = metrics.get_best_example_call(rep_calls, dim_key)
            if best_call:
                st.markdown(f"**📞 Your best {weakness['dimension_name']} call:**")
                st.markdown(f"- Score: {getattr(best_call.meddpicc_scores, dim_key)}/5")
                st.markdown(f"- Date: {styling.format_date(best_call.call_date)}")
                st.markdown(styling.format_gong_link_markdown(best_call.call_id, "Review This Call"))

    st.markdown("---")

    # Progress Tracking
    st.subheader("📈 Your Progress")

    if len(rep_calls) >= 2:
        progress_chart = build_progress_chart(rep_calls)
        if progress_chart:
            st.plotly_chart(progress_chart, use_container_width=True)
    else:
        st.info("Need at least 2 calls to show progress trends")

    st.markdown("---")

    # Recent Calls
    st.subheader("📋 Your Recent Calls")

    # Pagination for calls
    page_calls, total_pages, current_page = pagination.paginate(
        rep_calls,
        items_per_page=10,
        key_prefix="rep_calls"
    )

    st.markdown(f"Showing {len(page_calls)} of {len(rep_calls)} calls")
    pagination.show_pagination_controls(total_pages, current_page, key_prefix="rep_calls")

    st.markdown("---")

    for i, call in enumerate(page_calls, 1):
        score = call.meddpicc_scores.overall_score
        emoji = styling.get_score_emoji(score)

        with st.expander(
            f"{emoji} {styling.format_date(call.call_date)} - "
            f"Score: {styling.format_score(score)}"
        ):
            # MEDDPICC breakdown
            st.markdown("**MEDDPICC Breakdown:**")

            cols = st.columns(4)
            for i, dim in enumerate(styling.MEDDPICC_DIMENSIONS):
                dim_score = getattr(call.meddpicc_scores, dim)
                dim_abbrev = styling.format_dimension_abbrev(dim)
                col_idx = i % 4
                cols[col_idx].metric(label=dim_abbrev, value=dim_score)

            # Summary
            if call.meddpicc_summary:
                st.markdown("**Summary:**")
                st.markdown(f"> {call.meddpicc_summary}")

            # Link to Gong
            st.markdown(styling.format_gong_link_markdown(call.call_id))

    st.markdown("---")

    # Strengths
    if strengths:
        st.subheader("💪 Your Strengths")
        st.markdown("Areas where you're significantly above team average:")

        for strength in strengths:
            st.markdown(
                f"✓ **{strength['dimension_name']}** "
                f"({styling.format_score(strength['rep_score'])} vs team "
                f"{styling.format_score(strength['team_score'])}) - "
                f"You're {styling.format_delta(strength['delta'])} above average!"
            )

        st.info("💡 Consider coaching other reps on your strong dimensions")


if __name__ == "__main__":
    main()
