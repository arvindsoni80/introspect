"""
Introspect - Sales Coaching Dashboard

Main entry point for the Streamlit UI.
"""

import asyncio
import sys
from pathlib import Path

import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import load_settings
from src.sqlite_repository import SQLiteCallRepository
from utils import db_queries, styling

# Page config
st.set_page_config(
    page_title="Introspect - Sales Coaching Dashboard",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)


async def load_data():
    """Load all accounts from database."""
    # Create fresh repository connection (SQLite doesn't allow cross-thread usage)
    settings = load_settings()
    repo = SQLiteCallRepository(settings.sqlite_db_path)

    try:
        accounts = await repo.get_all_accounts()
        return accounts
    finally:
        await repo.close()


def main():
    """Main application."""

    # Title
    st.title("🎓 Introspect - Sales Coaching Dashboard")
    st.markdown("---")

    # Load data
    with st.spinner("Loading data from database..."):
        accounts = asyncio.run(load_data())

    if not accounts:
        st.warning("No accounts found in database. Run the analyzer first to populate data.")
        st.code("python main.py --sales-reps your@email.com")
        return

    # Get team stats
    team_stats = db_queries.get_team_stats(accounts)

    # Display high-level metrics
    st.subheader("📊 Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Discovery Calls",
            value=team_stats['total_discovery_calls']
        )

    with col2:
        st.metric(
            label="Accounts",
            value=team_stats['unique_accounts']
        )

    with col3:
        st.metric(
            label="Sales Reps",
            value=team_stats['unique_reps']
        )

    with col4:
        score = team_stats['avg_overall_score']
        emoji = styling.get_score_emoji(score)
        st.metric(
            label="Avg MEDDPICC Score",
            value=f"{emoji} {styling.format_score(score)}"
        )

    st.markdown("---")

    # Dimension scores
    st.subheader("🎯 Team MEDDPICC Breakdown")

    dim_scores = team_stats['avg_scores_by_dimension']

    # Create 2 columns for dimensions
    col1, col2 = st.columns(2)

    dimensions = styling.MEDDPICC_DIMENSIONS

    for i, dim in enumerate(dimensions):
        col = col1 if i < 4 else col2

        score = dim_scores.get(dim, 0)
        dim_name = styling.format_dimension_name(dim)
        emoji = styling.get_score_emoji(score)

        with col:
            st.metric(
                label=f"{emoji} {dim_name}",
                value=styling.format_score(score)
            )

    st.markdown("---")

    # Quick navigation
    st.info("💡 Use the sidebar to navigate to detailed dashboards:\n- **🎓 Team Coaching** - Team-wide insights and priorities\n- **👤 Rep Coaching** - Individual rep performance and focus areas\n- **🏢 Account Qualification** - Browse and analyze all accounts")


if __name__ == "__main__":
    main()
