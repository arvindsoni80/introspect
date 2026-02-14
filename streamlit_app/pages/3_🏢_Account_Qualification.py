"""Account Qualification Dashboard - Track deal health and qualification gaps."""

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
    page_title="Account Qualification - Introspect",
    page_icon="🏢",
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


def build_coverage_chart(account):
    """Build MEDDPICC coverage chart for an account."""
    dimensions = styling.MEDDPICC_DIMENSIONS
    dim_labels = [styling.format_dimension_abbrev(d) for d in dimensions]
    scores = [getattr(account.overall_meddpicc, d) for d in dimensions]

    colors = [styling.get_score_color(s) for s in scores]

    fig = go.Figure(go.Bar(
        x=dim_labels,
        y=scores,
        marker=dict(color=colors),
        text=[f"{s}" for s in scores],
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


def build_evolution_chart(account):
    """
    Build evolution chart showing when each dimension reached its maximum value.

    Shows dots/bubbles only at the call where each dimension hit its max score.
    """
    if len(account.calls) < 1:
        return None

    # Sort calls by date
    sorted_calls = sorted(account.calls, key=lambda c: c.call_date)

    dimensions = styling.MEDDPICC_DIMENSIONS
    dim_labels = [styling.format_dimension_name(d) for d in dimensions]

    # Find when each dimension reached its max
    max_points = []  # List of (date, dim_index, max_score, call_number)

    for dim_idx, dim in enumerate(dimensions):
        # Get max score for this dimension across all calls
        max_score = max(getattr(call.meddpicc_scores, dim) for call in sorted_calls)

        # Find first call where it reached this max
        for call_num, call in enumerate(sorted_calls, 1):
            score = getattr(call.meddpicc_scores, dim)
            if score == max_score:
                max_points.append({
                    'date': call.call_date,
                    'dim_index': dim_idx,
                    'dim_name': dim_labels[dim_idx],
                    'max_score': max_score,
                    'call_number': call_num
                })
                break  # Only mark the first time it reached max

    # Create scatter plot
    fig = go.Figure()

    # Add scatter points for each dimension's max
    for point in max_points:
        color = styling.get_score_color(point['max_score'])

        fig.add_trace(go.Scatter(
            x=[point['date']],
            y=[point['dim_index']],
            mode='markers',
            marker=dict(
                size=20 + (point['max_score'] * 5),  # Size based on score
                color=color,
                line=dict(color='white', width=2),
                symbol='circle'
            ),
            name=point['dim_name'],
            showlegend=False,
            hovertemplate=(
                f"<b>{point['dim_name']}</b><br>"
                f"Max Score: {point['max_score']}/5<br>"
                f"Call #{point['call_number']}<br>"
                "%{x|%b %d, %Y}<extra></extra>"
            )
        ))

    # Update layout
    fig.update_layout(
        title="When Did We Discover Each Dimension? (First time max score reached)",
        xaxis_title="Call Date",
        yaxis=dict(
            tickmode='array',
            tickvals=list(range(len(dimensions))),
            ticktext=dim_labels,
            title=""
        ),
        height=400,
        hovermode='closest'
    )

    return fig


def show_account_detail(account):
    """Show detailed account view in expander."""
    score = account.overall_meddpicc.overall_score
    emoji = styling.get_score_emoji(score)
    label = styling.get_score_label(score)

    st.markdown(f"## {emoji} {account.domain}")
    st.markdown(f"**Overall MEDDPICC:** {styling.format_score(score)} - {label}")
    st.markdown(f"**Discovery Calls:** {len(account.calls)}")
    st.markdown(f"**Last Updated:** {styling.format_date(account.updated_at)}")

    st.markdown("---")

    # MEDDPICC Coverage
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("### 📊 Current Coverage")
        coverage_chart = build_coverage_chart(account)
        st.plotly_chart(coverage_chart, use_container_width=True)

    with col2:
        st.markdown("### 🎯 Gaps to Close")
        gaps = metrics.get_dimension_gaps(account, threshold=4.0)

        if gaps:
            for dim_key, score, dim_name in gaps[:5]:  # Top 5 gaps
                gap_emoji = styling.get_score_emoji(score)
                st.markdown(f"{gap_emoji} **{dim_name}**: {score}/5")
        else:
            st.success("✅ All dimensions scored 4+!")

    st.markdown("---")

    # Evolution Chart (if multiple calls)
    if len(account.calls) >= 2:
        st.markdown("### 📈 Discovery Evolution")
        evolution_chart = build_evolution_chart(account)
        if evolution_chart:
            st.plotly_chart(evolution_chart, use_container_width=True)
        st.markdown("---")

    # Call History
    st.markdown("### 📞 Call History")

    for call in sorted(account.calls, key=lambda c: c.call_date, reverse=True):
        call_score = call.meddpicc_scores.overall_score
        call_emoji = styling.get_score_emoji(call_score)

        with st.expander(
            f"{call_emoji} {styling.format_date(call.call_date)} - "
            f"Score: {styling.format_score(call_score)} - {call.sales_rep.split('@')[0]}"
        ):
            # Sales rep
            st.markdown(f"**Sales Rep:** {call.sales_rep}")

            st.markdown("---")

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

            # Gong link
            st.markdown(styling.format_gong_link_markdown(call.call_id))

    st.markdown("---")

    # Next Steps
    st.markdown("### 💡 Recommended Next Steps")
    next_steps = metrics.generate_next_steps(account)

    for step in next_steps:
        st.markdown(f"- {step}")

    # Red flags
    red_flags = metrics.detect_account_red_flags(account)
    if red_flags:
        st.markdown("---")
        st.markdown("### 🚨 Red Flags")
        for flag in red_flags:
            st.warning(f"⚠️ {flag}")


def main():
    """Main account qualification dashboard."""

    st.title("🏢 Account Qualification Dashboard")

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
        index=3  # Default to all time for accounts
    )

    # Calculate date range
    days = date_options[date_selection]
    date_from = datetime.now() - timedelta(days=days) if days else None
    date_to = None

    # Load data
    with st.spinner("Loading accounts..."):
        accounts = asyncio.run(load_data(date_from, date_to))

    if not accounts:
        st.warning("No accounts found for the selected date range.")
        return

    # Get categorized accounts
    red_flags = db_queries.get_account_red_flags(accounts, min_calls=3, max_score=3.0)
    strong_accounts = db_queries.get_strong_accounts(accounts, min_score=4.0)
    moderate_accounts = db_queries.get_moderate_accounts(accounts, min_score=2.5, max_score=4.0)

    # Summary metrics
    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="🏢 Total Accounts",
            value=len(accounts)
        )

    with col2:
        st.metric(
            label="🟢 Strong (4+)",
            value=f"{len(strong_accounts)} ({len(strong_accounts)/len(accounts)*100:.0f}%)"
        )

    with col3:
        st.metric(
            label="🔴 Weak (<2.5)",
            value=f"{len(red_flags)} ({len(red_flags)/len(accounts)*100:.0f}%)"
        )

    st.markdown("---")

    # Categorize accounts for status
    red_flag_domains = {a.domain for a in red_flags}
    strong_domains = {a.domain for a in strong_accounts}
    moderate_domains = {a.domain for a in moderate_accounts}

    # Filter options
    st.markdown("### 📊 All Accounts")

    col1, col2 = st.columns([3, 1])
    with col1:
        filter_option = st.selectbox(
            "Filter by Status",
            options=["All Accounts", "🔴 Red Flags", "🟢 Strong (≥4.0)", "🟡 Moderate (2.5-4.0)"],
            index=0
        )
    with col2:
        sort_option = st.selectbox(
            "Sort by",
            options=["Score (High to Low)", "Score (Low to High)", "Most Calls", "Account Name"],
            index=0
        )

    # Filter accounts based on selection
    if filter_option == "🔴 Red Flags":
        filtered_accounts = red_flags
    elif filter_option == "🟢 Strong (≥4.0)":
        filtered_accounts = strong_accounts
    elif filter_option == "🟡 Moderate (2.5-4.0)":
        filtered_accounts = moderate_accounts
    else:
        filtered_accounts = accounts

    # Sort accounts
    if sort_option == "Score (High to Low)":
        filtered_accounts = sorted(filtered_accounts, key=lambda a: a.overall_meddpicc.overall_score, reverse=True)
    elif sort_option == "Score (Low to High)":
        filtered_accounts = sorted(filtered_accounts, key=lambda a: a.overall_meddpicc.overall_score)
    elif sort_option == "Most Calls":
        filtered_accounts = sorted(filtered_accounts, key=lambda a: len(a.calls), reverse=True)
    else:  # Account Name
        filtered_accounts = sorted(filtered_accounts, key=lambda a: a.domain)

    st.markdown("---")

    # Build table data
    if filtered_accounts:
        table_data = []
        for i, account in enumerate(filtered_accounts, 1):
            score = account.overall_meddpicc.overall_score

            # Determine status
            if account.domain in red_flag_domains:
                status = "🔴 Red Flag"
            elif account.domain in strong_domains:
                status = "🟢 Strong"
            elif account.domain in moderate_domains:
                status = "🟡 Moderate"
            else:
                status = "⚪ Other"

            # Find weakest dimension
            dim_scores = {dim: getattr(account.overall_meddpicc, dim) for dim in styling.MEDDPICC_DIMENSIONS}
            weakest_dim, weakest_score = min(dim_scores.items(), key=lambda x: x[1])
            key_gap = f"{styling.format_dimension_abbrev(weakest_dim)}: {weakest_score}"

            # Get most recent call for Gong link
            most_recent_call = sorted(account.calls, key=lambda c: c.call_date, reverse=True)[0]
            gong_url = styling.get_gong_call_link(most_recent_call.call_id)

            row = {
                "#": i,
                "Account": account.domain,
                "Score": f"{score:.1f}",
                "Status": status,
                "# Calls": len(account.calls),
                "Key Gap": key_gap,
                "Last Call": styling.format_date(account.updated_at),
                "Gong Link": gong_url,
                "_domain": account.domain  # Hidden column for click handling
            }
            table_data.append(row)

        # Convert to DataFrame
        df = pd.DataFrame(table_data)

        # Display table
        st.dataframe(
            df.drop(columns=['_domain']),
            column_config={
                "Gong Link": st.column_config.LinkColumn("Gong Link", display_text="🔗 View"),
                "Score": st.column_config.NumberColumn("Score", format="%.1f"),
            },
            hide_index=True,
            use_container_width=True
        )

        st.markdown(f"**Showing {len(filtered_accounts)} account(s)**")

        # Account selector for details
        st.markdown("---")
        st.markdown("### 🔍 View Account Details")

        selected_account_name = st.selectbox(
            "Select an account to view details",
            options=[""] + [a.domain for a in filtered_accounts],
            format_func=lambda x: "Choose an account..." if x == "" else x
        )

        if selected_account_name:
            # Find the selected account
            selected_account = next((a for a in filtered_accounts if a.domain == selected_account_name), None)

            if selected_account:
                st.markdown("---")
                show_account_detail(selected_account)
    else:
        st.info("No accounts found matching the selected filter.")
if __name__ == "__main__":
    main()
