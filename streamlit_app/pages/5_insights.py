"""Executive Insights Dashboard - Answer key questions about pipeline health and performance."""

import importlib
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional

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
    page_title="Insights - Introspect",
    page_icon="📊",
    layout="wide"
)


# ============================================================================
# Constants & Helpers
# ============================================================================

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


def get_account_health_score(account, repo: Repository) -> Tuple[float, str]:
    """Get current health score and stage for an account."""
    stage = account.current_stage
    if not stage or stage not in ["discovery", "trial", "negotiation"]:
        return None, None

    # Get most recent call for this stage
    query = """
        SELECT * FROM calls
        WHERE account_id = ? AND primary_stage = ?
        ORDER BY call_date DESC
        LIMIT 1
    """
    cursor = repo.conn.execute(query, (account.id, stage))
    row = cursor.fetchone()

    if not row:
        return None, None

    call = repo._row_to_call(row)

    # Get stage-specific score
    if stage == "discovery":
        scores = repo.get_call_meddpicc_scores(call.call_id)
        if scores:
            return scores.scores.overall_score, stage
    elif stage == "trial":
        scores = repo.get_call_trial_scores(call.call_id)
        if scores:
            return scores.scores.overall_score, stage
    elif stage == "negotiation":
        scores = repo.get_call_close_scores(call.call_id)
        if scores:
            return scores.scores.overall_score, stage

    return None, None


# ============================================================================
# Data Loading
# ============================================================================

def load_data(repo: Repository, stage: Optional[str] = None, segment: Optional[str] = None,
              date_from: Optional[datetime] = None, date_to: Optional[datetime] = None):
    """Load accounts from database with filtering."""
    # Get all accounts
    accounts = repo.list_accounts()

    # Filter by stage
    if stage and stage != "All":
        accounts = [a for a in accounts if a.current_stage == stage.lower()]

    # Filter by segment
    if segment and segment != "All":
        accounts = [a for a in accounts if a.primary_segment == segment.lower()]

    # Filter by date range (strip timezone for comparison)
    if date_from:
        accounts = [a for a in accounts if a.last_call_date and
                   (a.last_call_date.replace(tzinfo=None) if a.last_call_date.tzinfo else a.last_call_date) >= date_from]
    if date_to:
        accounts = [a for a in accounts if a.last_call_date and
                   (a.last_call_date.replace(tzinfo=None) if a.last_call_date.tzinfo else a.last_call_date) <= date_to]

    return accounts


def get_calls_for_account_stage(repo: Repository, account_id: int, stage: str) -> List:
    """Get calls for an account in a specific stage."""
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


def build_table_data(accounts: List, repo: Repository) -> List[Dict]:
    """Build table data with consistent columns (matching accounts page)."""
    table_data = []

    for i, account in enumerate(accounts, 1):
        account_stage = account.current_stage or "unknown"

        # Get calls for this account's current stage
        calls = get_calls_for_account_stage(repo, account.id, account_stage)

        if not calls:
            continue

        # Get most recent call
        most_recent_call = calls[0]

        # Format sales rep
        sales_rep = account.primary_sales_rep or "unknown"
        if "@" in sales_rep:
            sales_rep = sales_rep.split("@")[0]

        stage_emoji = STAGE_EMOJIS.get(account_stage, "📊")
        row = {
            "#": i,
            "Account": account.domain,
            "Stage": f"{stage_emoji} {account_stage.title()}",
            "Segment": (account.primary_segment or "unknown").title(),
            "Sales Rep": sales_rep,
            "# Calls": len(calls),
            "Days in Stage": account.days_in_current_stage() or 0,
            "Last Call": format_date(account.last_call_date),
            "Gong Link": format_gong_link(most_recent_call.call_id),
            "_account_id": account.id,
            "_stage": account_stage
        }

        # Add stage-specific columns
        if account_stage == "discovery":
            if hasattr(most_recent_call, 'meddpicc_scores'):
                score = most_recent_call.meddpicc_scores.overall_score
                row["Score"] = f"{score:.1f}"
                row["Status"] = f"{get_score_emoji(score)} {'Strong' if score >= 4 else 'Moderate' if score >= 2.5 else 'Weak'}"

                # Find weakest dimension
                dimensions = ["metrics", "economic_buyer", "decision_criteria", "decision_process",
                             "paper_process", "identify_pain", "champion", "competition"]
                dim_scores = {d: getattr(most_recent_call.meddpicc_scores, d) for d in dimensions}
                weakest = min(dim_scores.items(), key=lambda x: x[1])
                row["Key Gap"] = f"{weakest[0].replace('_', ' ').title()}: {weakest[1]}"

        elif account_stage == "trial":
            if hasattr(most_recent_call, 'trial_scores'):
                score = most_recent_call.trial_scores.overall_score
                health = most_recent_call.trial_scores.health_interpretation or "unknown"
                row["Score"] = f"{score:.1f}"
                row["Health"] = f"{HEALTH_EMOJIS.get(health, '⚪')} {health.title()}"
                row["Primary Concern"] = (most_recent_call.trial_scores.primary_concern_category or "none").title()
                row["Likelihood"] = (most_recent_call.trial_scores.likelihood_to_advance or "unknown").title()

        elif account_stage == "negotiation":
            if hasattr(most_recent_call, 'close_scores'):
                score = most_recent_call.close_scores.overall_score
                health = most_recent_call.close_scores.health_interpretation or "unknown"
                row["Score"] = f"{score:.1f}"
                row["Health"] = f"{HEALTH_EMOJIS.get(health, '⚪')} {health.title()}"
                row["Primary Concern"] = (most_recent_call.close_scores.primary_concern_category or "none").title()
                row["Likelihood"] = (most_recent_call.close_scores.likelihood_to_close or "unknown").title()

        elif account_stage == "closed":
            if hasattr(most_recent_call, 'winloss_analysis'):
                outcome = most_recent_call.winloss_analysis.outcome
                row["Outcome"] = f"{OUTCOME_EMOJIS.get(outcome, '⚪')} {outcome.title()}"
                row["Stage of Decision"] = (most_recent_call.winloss_analysis.stage_of_decision or "unknown").title()
                reasons = most_recent_call.winloss_analysis.primary_reasons or ""
                first_reason = reasons.split('\n')[0] if reasons else "N/A"
                row["Primary Reason"] = first_reason[:50] + "..." if len(first_reason) > 50 else first_reason

        table_data.append(row)

    return table_data


# ============================================================================
# Insight 1: At-Risk Deals
# ============================================================================

def show_at_risk_deals(accounts: List, repo: Repository):
    """Show at-risk deals that need immediate attention."""
    st.markdown("## 🚨 At-Risk Deals (Need Immediate Attention)")
    st.markdown("Accounts in **Trial** or **Negotiation** with health scores below 2.5")

    # Filter to at-risk accounts
    at_risk_accounts = []
    for account in accounts:
        if account.current_stage in ["trial", "negotiation"]:
            score, stage = get_account_health_score(account, repo)
            if score is not None and score < 2.5:
                at_risk_accounts.append(account)

    # Summary Panel
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("🔴 At-Risk Deals", len(at_risk_accounts))

    with col2:
        trial_count = sum(1 for a in at_risk_accounts if a.current_stage == "trial")
        st.metric("🧪 In Trial", trial_count)

    with col3:
        neg_count = sum(1 for a in at_risk_accounts if a.current_stage == "negotiation")
        st.metric("💼 In Negotiation", neg_count)

    with col4:
        critical_count = sum(1 for a in at_risk_accounts if (get_account_health_score(a, repo)[0] or 0) < 2.0)
        st.metric("⚠️ Critical (<2.0)", critical_count)

    st.markdown("---")

    if not at_risk_accounts:
        st.success("✅ No at-risk deals found! All active deals have health scores ≥ 2.5")
        return

    # Build detailed table using consistent structure
    st.markdown("### 📋 Account Details")

    # Clear selection button
    if st.button("🔄 Clear Selection", key="clear_atrisk"):
        if 'selected_account_domain' in st.session_state:
            del st.session_state['selected_account_domain']
            st.rerun()

    table_data = build_table_data(at_risk_accounts, repo)

    if not table_data:
        st.info("No detailed data available for at-risk accounts.")
        return

    # Display table
    df = pd.DataFrame(table_data)
    display_columns = [col for col in df.columns if not col.startswith('_')]
    display_df = df[display_columns]

    st.markdown("**Click on a row to view full account details**")

    event = st.dataframe(
        display_df,
        column_config={
            "Gong Link": st.column_config.LinkColumn("Gong Link", display_text="🔗 View"),
        },
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    st.markdown(f"**Showing {len(table_data)} at-risk account(s)**")

    # Handle row selection with session state to persist across sorts
    if event.selection.rows:
        selected_row_idx = event.selection.rows[0]
        # Store the Account domain instead of ID to match after sorting
        selected_account_domain = table_data[selected_row_idx]['Account']
        st.session_state['selected_account_domain'] = selected_account_domain

    # Show selected account details from session state
    if 'selected_account_domain' in st.session_state:
        selected_account = next(
            (a for a in at_risk_accounts if a.domain == st.session_state['selected_account_domain']),
            None
        )

        if selected_account:
            st.markdown("---")
            accounts_module = importlib.import_module("2_accounts")
            accounts_module.show_account_detail(selected_account, repo)


# ============================================================================
# Insight 2: Forecast by Confidence Level
# ============================================================================

def show_forecast_confidence(accounts: List, repo: Repository):
    """Show pipeline forecast grouped by confidence level."""
    st.markdown("## 📈 Forecast by Confidence Level")
    st.markdown("Active deals grouped by health score (High: ≥4.0, Medium: 2.5-4.0, Low: <2.5)")

    # Categorize accounts by confidence
    high_confidence = []  # >= 4.0
    medium_confidence = []  # 2.5 - 4.0
    low_confidence = []  # < 2.5
    no_score = []  # Discovery or no score available

    for account in accounts:
        if account.current_stage in ["trial", "negotiation"]:
            score, stage = get_account_health_score(account, repo)
            if score is not None:
                if score >= 4.0:
                    high_confidence.append(account)
                elif score >= 2.5:
                    medium_confidence.append(account)
                else:
                    low_confidence.append(account)
            else:
                no_score.append(account)
        elif account.current_stage == "discovery":
            no_score.append(account)

    # Summary Panel
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("🟢 High Confidence (≥4.0)", len(high_confidence))
        st.caption("Historically ~75% win rate")

    with col2:
        st.metric("🟡 Medium Confidence (2.5-4.0)", len(medium_confidence))
        st.caption("Historically ~45% win rate")

    with col3:
        st.metric("🔴 Low Confidence (<2.5)", len(low_confidence))
        st.caption("Historically ~15% win rate")

    with col4:
        st.metric("⚪ Discovery/No Score", len(no_score))
        st.caption("Early stage")

    st.markdown("---")

    # Confidence distribution chart
    fig = go.Figure(data=[go.Bar(
        x=["High (≥4.0)", "Medium (2.5-4.0)", "Low (<2.5)", "Discovery/No Score"],
        y=[len(high_confidence), len(medium_confidence), len(low_confidence), len(no_score)],
        marker=dict(color=["#2ecc71", "#f39c12", "#e74c3c", "#95a5a6"]),
        text=[len(high_confidence), len(medium_confidence), len(low_confidence), len(no_score)],
        textposition='auto',
    )])

    fig.update_layout(
        title="Pipeline Distribution by Confidence Level",
        xaxis_title="Confidence Level",
        yaxis_title="Number of Accounts",
        height=400,
        showlegend=False
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Select which group to view
    view_options = [
        f"🟢 High Confidence ({len(high_confidence)})",
        f"🟡 Medium Confidence ({len(medium_confidence)})",
        f"🔴 Low Confidence ({len(low_confidence)})",
        f"⚪ Discovery/No Score ({len(no_score)})"
    ]

    selected_view = st.selectbox("View Details For:", view_options)

    # Determine which list to show
    if "High Confidence" in selected_view:
        accounts_to_show = high_confidence
        title = "🟢 High Confidence Accounts (≥4.0)"
    elif "Medium Confidence" in selected_view:
        accounts_to_show = medium_confidence
        title = "🟡 Medium Confidence Accounts (2.5-4.0)"
    elif "Low Confidence" in selected_view:
        accounts_to_show = low_confidence
        title = "🔴 Low Confidence Accounts (<2.5)"
    else:
        accounts_to_show = no_score
        title = "⚪ Discovery/No Score Accounts"

    if not accounts_to_show:
        st.info(f"No accounts in this category.")
        return

    # Build table using consistent structure
    st.markdown(f"### {title}")
    table_data = build_table_data(accounts_to_show, repo)

    if not table_data:
        st.info("No detailed data available.")
        return

    # Display table
    df = pd.DataFrame(table_data)
    display_columns = [col for col in df.columns if not col.startswith('_')]
    display_df = df[display_columns]

    st.markdown("**Click on a row to view full account details**")

    event = st.dataframe(
        display_df,
        column_config={
            "Gong Link": st.column_config.LinkColumn("Gong Link", display_text="🔗 View"),
        },
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    st.markdown(f"**Showing {len(table_data)} account(s)**")

    # Handle row selection with session state to persist across sorts
    if event.selection.rows:
        selected_row_idx = event.selection.rows[0]
        selected_account_domain = table_data[selected_row_idx]['Account']
        st.session_state['selected_account_domain_fc'] = selected_account_domain

    # Show selected account details from session state
    if 'selected_account_domain_fc' in st.session_state:
        selected_account = next(
            (a for a in accounts_to_show if a.domain == st.session_state['selected_account_domain_fc']),
            None
        )

        if selected_account:
            st.markdown("---")
            accounts_module = importlib.import_module("2_accounts")
            accounts_module.show_account_detail(selected_account, repo)


# ============================================================================
# Insight 3: Qualification Quality (MEDDPICC Gaps)
# ============================================================================

def show_qualification_gaps(accounts: List, repo: Repository):
    """Show discovery accounts with MEDDPICC qualification gaps."""
    st.markdown("## 🏆 Qualification Quality (MEDDPICC Gaps)")
    st.markdown("Discovery stage accounts with low MEDDPICC scores or specific dimension gaps")

    # Filter to discovery accounts
    discovery_accounts = [a for a in accounts if a.current_stage == "discovery"]

    if not discovery_accounts:
        st.info("No accounts currently in Discovery stage.")
        return

    # Analyze MEDDPICC scores
    weak_qualification = []  # Overall score < 3.0
    dimension_gaps = []  # Any dimension < 2.0

    for account in discovery_accounts:
        score, _ = get_account_health_score(account, repo)
        if score is None:
            continue

        # Check for weak overall qualification
        if score < 3.0:
            weak_qualification.append(account)

        # Check for dimension gaps (any dimension < 2.0)
        query = """
            SELECT * FROM calls
            WHERE account_id = ? AND primary_stage = 'discovery'
            ORDER BY call_date DESC
            LIMIT 1
        """
        cursor = repo.conn.execute(query, (account.id,))
        row = cursor.fetchone()

        if not row:
            continue

        call = repo._row_to_call(row)
        scores = repo.get_call_meddpicc_scores(call.call_id)

        if not scores:
            continue

        medd_scores = scores.scores

        dimensions = {
            "Metrics": medd_scores.metrics,
            "Economic Buyer": medd_scores.economic_buyer,
            "Decision Criteria": medd_scores.decision_criteria,
            "Decision Process": medd_scores.decision_process,
            "Paper Process": medd_scores.paper_process,
            "Identify Pain": medd_scores.identify_pain,
            "Champion": medd_scores.champion,
            "Competition": medd_scores.competition
        }

        weak_dims = [dim for dim, score in dimensions.items() if score < 2.0]

        if weak_dims:
            dimension_gaps.append(account)

    # Summary Panel
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("📊 Total Discovery", len(discovery_accounts))

    with col2:
        st.metric("🔴 Weak Qualification (<3.0)", len(weak_qualification))

    with col3:
        st.metric("⚠️ Critical Gaps (dim <2.0)", len(dimension_gaps))

    with col4:
        strong_count = len([a for a in discovery_accounts if a not in weak_qualification])
        st.metric("🟢 Strong Qualification (≥3.0)", strong_count)

    st.markdown("---")

    # View selector
    view_options = [
        f"🔴 Weak Qualification (<3.0) - {len(weak_qualification)}",
        f"⚠️ Critical Dimension Gaps - {len(dimension_gaps)}"
    ]

    selected_view = st.selectbox("View:", view_options)

    # Determine which to show
    if "Weak Qualification" in selected_view:
        accounts_to_show = weak_qualification
        title = "🔴 Weakly Qualified Accounts (MEDDPICC <3.0)"
    else:
        accounts_to_show = dimension_gaps
        title = "⚠️ Accounts with Critical Dimension Gaps (Any dimension <2.0)"

    if not accounts_to_show:
        st.success("✅ No qualification issues found!")
        return

    # Build table using consistent structure
    st.markdown(f"### {title}")
    table_data = build_table_data(accounts_to_show, repo)

    if not table_data:
        st.info("No detailed data available.")
        return

    # Display table
    df = pd.DataFrame(table_data)
    display_columns = [col for col in df.columns if not col.startswith('_')]
    display_df = df[display_columns]

    st.markdown("**Click on a row to view full account details**")

    event = st.dataframe(
        display_df,
        column_config={
            "Gong Link": st.column_config.LinkColumn("Gong Link", display_text="🔗 View"),
        },
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    st.markdown(f"**Showing {len(table_data)} account(s)**")

    # Handle row selection with session state to persist across sorts
    if event.selection.rows:
        selected_row_idx = event.selection.rows[0]
        selected_account_domain = table_data[selected_row_idx]['Account']
        st.session_state['selected_account_domain_qg'] = selected_account_domain

    # Show selected account details from session state
    if 'selected_account_domain_qg' in st.session_state:
        selected_account = next(
            (a for a in accounts_to_show if a.domain == st.session_state['selected_account_domain_qg']),
            None
        )

        if selected_account:
            st.markdown("---")
            accounts_module = importlib.import_module("2_accounts")
            accounts_module.show_account_detail(selected_account, repo)


# ============================================================================
# Insight 4: Win/Loss Patterns
# ============================================================================

def show_win_loss_patterns(accounts: List, repo: Repository):
    """Show win/loss analysis patterns."""
    st.markdown("## 💰 Win/Loss Patterns & Analysis")
    st.markdown("Analyze closed deals to understand why we win and why we lose")

    # Filter to closed accounts
    closed_accounts = [a for a in accounts if a.current_stage == "closed"]

    if not closed_accounts:
        st.info("No closed deals found yet.")
        return

    # Categorize by outcome
    won_deals = []
    lost_deals = []

    for account in closed_accounts:
        query = """
            SELECT * FROM calls
            WHERE account_id = ? AND primary_stage = 'closed'
            ORDER BY call_date DESC
            LIMIT 1
        """
        cursor = repo.conn.execute(query, (account.id,))
        row = cursor.fetchone()

        if not row:
            continue

        call = repo._row_to_call(row)
        analysis = repo.get_call_win_loss_analysis(call.call_id)

        if not analysis:
            continue

        if analysis.analysis.outcome == "won":
            won_deals.append(account)
        else:
            lost_deals.append(account)

    # Summary Panel
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)

    total = len(won_deals) + len(lost_deals)
    win_rate = (len(won_deals) / total * 100) if total > 0 else 0

    with col1:
        st.metric("📊 Total Closed", total)

    with col2:
        st.metric("✅ Won", len(won_deals))

    with col3:
        st.metric("❌ Lost", len(lost_deals))

    with col4:
        st.metric("📈 Win Rate", f"{win_rate:.1f}%")

    st.markdown("---")

    # Win/Loss chart
    fig = go.Figure(data=[go.Pie(
        labels=["Won", "Lost"],
        values=[len(won_deals), len(lost_deals)],
        marker=dict(colors=["#2ecc71", "#e74c3c"]),
        hole=0.4,
        textinfo='label+value+percent'
    )])

    fig.update_layout(
        title="Win/Loss Distribution",
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # View selector
    view_options = [
        f"✅ Won Deals ({len(won_deals)})",
        f"❌ Lost Deals ({len(lost_deals)})"
    ]

    selected_view = st.selectbox("View:", view_options)

    # Determine which to show
    if "Won Deals" in selected_view:
        deals_to_show = won_deals
        title = "✅ Won Deals"
    else:
        deals_to_show = lost_deals
        title = "❌ Lost Deals"

    if not deals_to_show:
        st.info(f"No deals in this category.")
        return

    # Build table using consistent structure
    st.markdown(f"### {title}")
    table_data = build_table_data(deals_to_show, repo)

    if not table_data:
        st.info("No detailed data available.")
        return

    # Display table
    df = pd.DataFrame(table_data)
    display_columns = [col for col in df.columns if not col.startswith('_')]
    display_df = df[display_columns]

    st.markdown("**Click on a row to view full account details**")

    event = st.dataframe(
        display_df,
        column_config={
            "Gong Link": st.column_config.LinkColumn("Gong Link", display_text="🔗 View"),
        },
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    st.markdown(f"**Showing {len(table_data)} deal(s)**")

    # Handle row selection with session state to persist across sorts
    if event.selection.rows:
        selected_row_idx = event.selection.rows[0]
        selected_account_domain = table_data[selected_row_idx]['Account']
        st.session_state['selected_account_domain_wl'] = selected_account_domain

    # Show selected account details from session state
    if 'selected_account_domain_wl' in st.session_state:
        selected_account = next(
            (a for a in deals_to_show if a.domain == st.session_state['selected_account_domain_wl']),
            None
        )

        if selected_account:
            st.markdown("---")
            accounts_module = importlib.import_module("2_accounts")
            accounts_module.show_account_detail(selected_account, repo)


# ============================================================================
# Main App
# ============================================================================

def main():
    """Main insights dashboard."""
    st.title("📊 Executive Insights")
    st.markdown("Answer key questions about pipeline health, forecast accuracy, and deal performance")

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
            index=3  # Default to all time
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

        st.sidebar.markdown("---")

        # Insight selector
        insight_options = [
            "🚨 At-Risk Deals (Need Immediate Attention)",
            "📈 Forecast by Confidence Level",
            "🏆 Qualification Quality (MEDDPICC Gaps)",
            "💰 Win/Loss Patterns & Analysis"
        ]

        selected_insight = st.selectbox(
            "Select Executive Question:",
            options=insight_options,
            index=0
        )

        st.markdown("---")

        # Load filtered data
        accounts = load_data(
            repo,
            stage=stage_selection if stage_selection != "All" else None,
            segment=segment_selection.lower() if segment_selection != "All" else None,
            date_from=date_from,
            date_to=date_to
        )

        # Show selected insight
        if selected_insight == "🚨 At-Risk Deals (Need Immediate Attention)":
            show_at_risk_deals(accounts, repo)

        elif selected_insight == "📈 Forecast by Confidence Level":
            show_forecast_confidence(accounts, repo)

        elif selected_insight == "🏆 Qualification Quality (MEDDPICC Gaps)":
            show_qualification_gaps(accounts, repo)

        elif selected_insight == "💰 Win/Loss Patterns & Analysis":
            show_win_loss_patterns(accounts, repo)

    finally:
        db.close()


if __name__ == "__main__":
    main()
