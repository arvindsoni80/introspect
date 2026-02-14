"""Team Coaching Dashboard - Identify team-wide coaching opportunities."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config import load_settings
from src.sqlite_repository import SQLiteCallRepository
from streamlit_app.utils import db_queries, metrics, styling

# Page config
st.set_page_config(
    page_title="Team Coaching - Introspect",
    page_icon="🎓",
    layout="wide"
)


async def load_data(date_from=None, date_to=None):
    """Load accounts from database with optional date filtering."""
    # Create fresh repository connection (SQLite doesn't allow cross-thread usage)
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


def build_heatmap(rep_comparison):
    """Build MEDDPICC heatmap (rep x dimension)."""
    if not rep_comparison:
        return None

    # Prepare data for heatmap
    reps = [r['rep_email'].split('@')[0] for r in rep_comparison]  # Just username
    dimensions = styling.MEDDPICC_DIMENSIONS

    # Build matrix
    data = []
    for dim in dimensions:
        row = []
        for rep in rep_comparison:
            score = rep['avg_scores_by_dimension'].get(dim, 0)
            row.append(score)
        data.append(row)

    # Dimension labels (abbreviated)
    dim_labels = [styling.format_dimension_abbrev(d) for d in dimensions]

    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=data,
        x=reps,
        y=dim_labels,
        colorscale=[
            [0.0, styling.COLORS['score_weak']],
            [0.5, styling.COLORS['score_moderate']],
            [1.0, styling.COLORS['score_strong']]
        ],
        zmid=2.5,
        zmin=0,
        zmax=5,
        text=[[f"{val:.1f}" for val in row] for row in data],
        texttemplate="%{text}",
        textfont={"size": 12},
        colorbar=dict(title="Score", len=0.5),
        hovertemplate="<b>%{y}</b> - %{x}<br>Score: %{z:.1f}<extra></extra>"
    ))

    fig.update_layout(
        title="MEDDPICC Heatmap (Rep × Dimension)",
        xaxis_title="Sales Rep",
        yaxis_title="MEDDPICC Dimension",
        height=400,
        margin=dict(l=80, r=80, t=60, b=80)
    )

    return fig


def build_trend_chart(accounts, group_by='week'):
    """Build time series chart showing score trends."""
    time_series = db_queries.get_time_series(accounts, group_by=group_by)

    if not time_series:
        return None

    # Convert to DataFrame
    df = pd.DataFrame(time_series)

    # Create line chart
    fig = go.Figure()

    # Overall score line
    fig.add_trace(go.Scatter(
        x=df['period'],
        y=df['avg_overall_score'],
        mode='lines+markers',
        name='Overall',
        line=dict(color=styling.COLORS['info'], width=3),
        marker=dict(size=8)
    ))

    fig.update_layout(
        title="Team Discovery Score Trend",
        xaxis_title="Period",
        yaxis_title="Average Score",
        yaxis_range=[0, 5],
        height=350,
        hovermode='x unified'
    )

    return fig


def main():
    """Main team coaching dashboard."""

    st.title("🎓 Team Discovery Coaching Dashboard")

    # Sidebar: Date filter
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

    # Get team stats
    team_stats = db_queries.get_team_stats(accounts)
    rep_comparison = db_queries.get_rep_comparison(accounts)

    # Header metrics
    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="📊 Discovery Calls",
            value=team_stats['total_discovery_calls']
        )

    with col2:
        st.metric(
            label="🏢 Accounts",
            value=team_stats['unique_accounts']
        )

    with col3:
        st.metric(
            label="👥 Sales Reps",
            value=team_stats['unique_reps']
        )

    with col4:
        score = team_stats['avg_overall_score']
        emoji = styling.get_score_emoji(score)
        st.metric(
            label="🎯 Avg MEDDPICC",
            value=f"{emoji} {styling.format_score(score)}"
        )

    st.markdown("---")

    # Strengths and Weaknesses
    st.subheader("Team Performance Overview")

    dim_scores = team_stats['avg_scores_by_dimension']

    # Sort dimensions by score
    sorted_dims = sorted(dim_scores.items(), key=lambda x: x[1], reverse=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🟢 Where We're Strong")
        for dim, score in sorted_dims[:3]:
            dim_name = styling.format_dimension_name(dim)
            emoji = styling.get_score_emoji(score)
            st.markdown(f"{emoji} **{dim_name}**: {styling.format_score(score)}")

    with col2:
        st.markdown("### 🔴 Where We're Weak")
        for dim, score in sorted_dims[-3:]:
            dim_name = styling.format_dimension_name(dim)
            emoji = styling.get_score_emoji(score)
            st.markdown(f"{emoji} **{dim_name}**: {styling.format_score(score)}")

    st.markdown("---")

    # MEDDPICC Heatmap
    st.subheader("MEDDPICC Heatmap")
    st.markdown("Click on cells to see details. Darker green = stronger performance.")

    heatmap = build_heatmap(rep_comparison)
    if heatmap:
        st.plotly_chart(heatmap, use_container_width=True)
    else:
        st.info("Not enough data for heatmap")

    st.markdown("---")

    # Coaching Priorities
    st.subheader("🎯 Top Coaching Priorities")
    st.markdown("Focus on these areas to improve team-wide discovery quality.")

    priorities = metrics.generate_coaching_priorities(team_stats, top_n=3)

    for i, priority in enumerate(priorities, 1):
        severity_emoji = {
            'critical': '🔴',
            'needs_work': '🟡',
            'moderate': '🟠'
        }
        emoji = severity_emoji.get(priority['severity'], '⚠️')

        with st.expander(
            f"{emoji} **{i}. {priority['dimension_name']}** "
            f"(Avg: {styling.format_score(priority['score'])})",
            expanded=(i == 1)  # Expand first priority
        ):
            st.markdown(f"**Observation:** {priority['observation']}")

            # Find best example call for this dimension
            all_calls = []
            for account in accounts:
                all_calls.extend(account.calls)

            if all_calls:
                best_call = metrics.get_best_example_call(all_calls, priority['dimension'])

                if best_call:
                    st.markdown(f"**📞 Best Example Call:**")
                    st.markdown(
                        f"- Score: {getattr(best_call.meddpicc_scores, priority['dimension'])}/5"
                    )
                    st.markdown(f"- Rep: {best_call.sales_rep}")
                    st.markdown(
                        f"- Date: {styling.format_date(best_call.call_date)}"
                    )
                    st.markdown(styling.format_gong_link_markdown(best_call.call_id))

                    # Show the reasoning
                    if best_call.analysis_notes:
                        note = getattr(best_call.analysis_notes, priority['dimension'], "")
                        if note:
                            st.markdown(f"**Why this is a good example:**")
                            st.markdown(f"> {note[:300]}...")

    st.markdown("---")

    # Improvement Tracking
    st.subheader("📈 Team Improvement Tracking")
    st.markdown("Track average MEDDPICC scores over time.")

    trend_chart = build_trend_chart(accounts, group_by='week')
    if trend_chart:
        st.plotly_chart(trend_chart, use_container_width=True)
    else:
        st.info("Not enough historical data for trend chart")

    st.markdown("---")

    # Training Examples
    st.subheader("💡 Training Examples - Learn from Success")

    all_calls = []
    for account in accounts:
        all_calls.extend(account.calls)

    if all_calls:
        # Get top 3 weakest dimensions
        weak_dimensions = [p['dimension'] for p in priorities[:3]]
        weak_dim_names = [p['dimension_name'] for p in priorities[:3]]

        # Top 10 Calls in Weak Areas
        st.markdown("### 📞 Top 10 Calls Excelling in Our Weak Areas")
        st.markdown(f"Calls that performed well in: **{', '.join(weak_dim_names)}**")

        top_calls = metrics.get_top_calls_in_weak_areas(all_calls, weak_dimensions, top_n=10)

        if top_calls:
            # Build table data
            table_data = []
            for i, call in enumerate(top_calls, 1):
                # Calculate average score in weak dimensions
                weak_scores = [getattr(call.meddpicc_scores, dim) for dim in weak_dimensions]
                avg_weak_score = sum(weak_scores) / len(weak_scores)

                # Get individual weak dimension scores
                weak_scores_str = " | ".join([
                    f"{styling.format_dimension_abbrev(dim)}: {getattr(call.meddpicc_scores, dim)}"
                    for dim in weak_dimensions
                ])

                gong_url = styling.get_gong_call_link(call.call_id)

                row = {
                    "#": i,
                    "Date": styling.format_date(call.call_date),
                    "Sales Rep": call.sales_rep.split('@')[0],
                    "Weak Area Avg": f"{avg_weak_score:.1f}",
                    "Overall": f"{call.meddpicc_scores.overall_score:.1f}",
                    "Weak Scores": weak_scores_str,
                    "Gong Link": gong_url
                }
                table_data.append(row)

            # Convert to DataFrame
            df = pd.DataFrame(table_data)

            # Display with clickable links
            st.dataframe(
                df,
                column_config={
                    "Gong Link": st.column_config.LinkColumn("Gong Link", display_text="🔗 Review")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No example calls found")

        st.markdown("---")

        # Top 10 Accounts with Best Discovery
        st.markdown("### 🏢 Top 10 Accounts with Best Overall Discovery")
        st.markdown("Accounts demonstrating excellent multi-call discovery execution")

        top_accounts = metrics.get_top_accounts_by_discovery(accounts, top_n=10)

        if top_accounts:
            # Build table data
            table_data = []
            for i, account in enumerate(top_accounts, 1):
                score = account.overall_meddpicc.overall_score

                # Get top 3 MEDDPICC scores for this account
                dim_scores = {
                    dim: getattr(account.overall_meddpicc, dim)
                    for dim in styling.MEDDPICC_DIMENSIONS
                }
                top_dims = sorted(dim_scores.items(), key=lambda x: x[1], reverse=True)[:3]
                top_dims_str = " | ".join([
                    f"{styling.format_dimension_abbrev(dim)}: {score}"
                    for dim, score in top_dims
                ])

                # Get most recent call link
                most_recent_call = sorted(account.calls, key=lambda c: c.call_date, reverse=True)[0]
                gong_url = styling.get_gong_call_link(most_recent_call.call_id)

                row = {
                    "#": i,
                    "Account": account.domain,
                    "Score": f"{score:.1f}",
                    "# Calls": len(account.calls),
                    "Top 3 Dimensions": top_dims_str,
                    "Most Recent Call": styling.format_date(most_recent_call.call_date),
                    "Gong Link": gong_url
                }
                table_data.append(row)

            # Convert to DataFrame
            df = pd.DataFrame(table_data)

            # Display with clickable links
            st.dataframe(
                df,
                column_config={
                    "Gong Link": st.column_config.LinkColumn("Gong Link", display_text="🔗 Review")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No accounts found")


if __name__ == "__main__":
    main()
