"""Account Qualification Dashboard - Track deal health and qualification gaps."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

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

    # Filter buttons
    view_mode = st.radio(
        "View",
        options=["🔴 Red Flags", "🟢 Strong", "🟡 Moderate", "📋 All"],
        horizontal=True
    )

    st.markdown("---")

    # Show accounts based on view mode
    if view_mode == "🔴 Red Flags":
        st.subheader("🔴 Red Flags - Need Attention")
        st.markdown(f"**{len(red_flags)} accounts** with weak qualification after multiple calls")

        if not red_flags:
            st.info("No red flag accounts found!")
        else:
            # Pagination
            page_accounts, total_pages, current_page = pagination.paginate(
                red_flags,
                items_per_page=10,
                key_prefix="red_flags"
            )

            st.markdown(f"Showing {len(page_accounts)} of {len(red_flags)} accounts")
            pagination.show_pagination_controls(total_pages, current_page, key_prefix="red_flags")

            st.markdown("---")

            for account in page_accounts:
                score = account.overall_meddpicc.overall_score
                emoji = styling.get_score_emoji(score)
                flags = metrics.detect_account_red_flags(account)

                with st.expander(
                    f"{emoji} **{account.domain}** - Score: {styling.format_score(score)} "
                    f"({len(account.calls)} calls)",
                    expanded=False
                ):
                    if flags:
                        st.markdown("**⚠️ Issues:**")
                        for flag in flags:
                            st.markdown(f"- {flag}")

                    st.markdown("---")

                    # Quick stats
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Calls", len(account.calls))
                    with col2:
                        st.metric("Score", styling.format_score(score))
                    with col3:
                        st.metric("Last Call", styling.format_date(account.updated_at))

                    # Show button to see full details
                    if st.button(f"View Full Details", key=f"details_{account.domain}"):
                        st.session_state[f'show_detail_{account.domain}'] = True

                    if st.session_state.get(f'show_detail_{account.domain}', False):
                        show_account_detail(account)

    elif view_mode == "🟢 Strong":
        st.subheader("🟢 Strong Qualification - Keep Pushing")
        st.markdown(f"**{len(strong_accounts)} accounts** with score ≥ 4.0")

        if not strong_accounts:
            st.info("No strong accounts found yet. Focus on improving discovery!")
        else:
            # Pagination
            page_accounts, total_pages, current_page = pagination.paginate(
                strong_accounts,
                items_per_page=10,
                key_prefix="strong"
            )

            st.markdown(f"Showing {len(page_accounts)} of {len(strong_accounts)} accounts")
            pagination.show_pagination_controls(total_pages, current_page, key_prefix="strong")

            st.markdown("---")

            for account in page_accounts:
                score = account.overall_meddpicc.overall_score
                emoji = styling.get_score_emoji(score)

                with st.expander(
                    f"{emoji} **{account.domain}** - Score: {styling.format_score(score)} "
                    f"({len(account.calls)} calls)"
                ):
                    # Quick stats
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Calls", len(account.calls))
                    with col2:
                        st.metric("Score", styling.format_score(score))
                    with col3:
                        st.metric("Last Call", styling.format_date(account.updated_at))

                    # Strengths
                    st.markdown("**✅ Strengths:**")
                    for dim in styling.MEDDPICC_DIMENSIONS:
                        dim_score = getattr(account.overall_meddpicc, dim)
                        if dim_score >= 4:
                            dim_name = styling.format_dimension_name(dim)
                            st.markdown(f"- {dim_name}: {dim_score}/5")

                    # Show button to see full details
                    if st.button(f"View Full Details", key=f"details_{account.domain}"):
                        st.session_state[f'show_detail_{account.domain}'] = True

                    if st.session_state.get(f'show_detail_{account.domain}', False):
                        show_account_detail(account)

    elif view_mode == "🟡 Moderate":
        st.subheader("🟡 Moderate - Needs More Discovery")
        st.markdown(f"**{len(moderate_accounts)} accounts** with score 2.5-4.0")

        if not moderate_accounts:
            st.info("No moderate accounts found.")
        else:
            # Pagination
            page_accounts, total_pages, current_page = pagination.paginate(
                moderate_accounts,
                items_per_page=10,
                key_prefix="moderate"
            )

            st.markdown(f"Showing {len(page_accounts)} of {len(moderate_accounts)} accounts")
            pagination.show_pagination_controls(total_pages, current_page, key_prefix="moderate")

            st.markdown("---")

            for account in page_accounts:
                score = account.overall_meddpicc.overall_score
                emoji = styling.get_score_emoji(score)

                with st.expander(
                    f"{emoji} **{account.domain}** - Score: {styling.format_score(score)} "
                    f"({len(account.calls)} calls)"
                ):
                    # Quick stats
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Calls", len(account.calls))
                    with col2:
                        st.metric("Score", styling.format_score(score))
                    with col3:
                        st.metric("Last Call", styling.format_date(account.updated_at))

                    # Gaps
                    gaps = metrics.get_dimension_gaps(account, threshold=4.0)
                    if gaps:
                        st.markdown("**Focus on:**")
                        for dim_key, dim_score, dim_name in gaps[:3]:
                            st.markdown(f"- {dim_name}: {dim_score}/5")

                    # Show button to see full details
                    if st.button(f"View Full Details", key=f"details_{account.domain}"):
                        st.session_state[f'show_detail_{account.domain}'] = True

                    if st.session_state.get(f'show_detail_{account.domain}', False):
                        show_account_detail(account)

    else:  # All accounts
        st.subheader("📋 All Accounts")

        # Sort by score
        sorted_accounts = sorted(accounts, key=lambda a: a.overall_meddpicc.overall_score, reverse=True)

        # Pagination
        page_accounts, total_pages, current_page = pagination.paginate(
            sorted_accounts,
            items_per_page=10,
            key_prefix="all"
        )

        st.markdown(f"Showing {len(page_accounts)} of {len(sorted_accounts)} accounts")
        pagination.show_pagination_controls(total_pages, current_page, key_prefix="all")

        st.markdown("---")

        for account in page_accounts:
            score = account.overall_meddpicc.overall_score
            emoji = styling.get_score_emoji(score)

            with st.expander(
                f"{emoji} **{account.domain}** - Score: {styling.format_score(score)} "
                f"({len(account.calls)} calls)"
            ):
                # Quick stats
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Calls", len(account.calls))
                with col2:
                    st.metric("Score", styling.format_score(score))
                with col3:
                    st.metric("Last Call", styling.format_date(account.updated_at))

                # Show button to see full details
                if st.button(f"View Full Details", key=f"details_{account.domain}"):
                    st.session_state[f'show_detail_{account.domain}'] = True

                if st.session_state.get(f'show_detail_{account.domain}', False):
                    show_account_detail(account)


if __name__ == "__main__":
    main()
