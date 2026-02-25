"""Summary Page - Executive overview of sales activity and engagement."""

import sys
from datetime import datetime, timedelta, date as date_type
from pathlib import Path
from typing import Dict, Optional, List, Tuple

import streamlit as st
import plotly.graph_objects as go

# Try to import shadcn-ui components, fall back to native Streamlit if not available
try:
    import streamlit_shadcn_ui as ui
    SHADCN_AVAILABLE = True
except ImportError:
    SHADCN_AVAILABLE = False

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core import Config
from src.data import Database, Repository

# Page config
st.set_page_config(
    page_title="Summary - Introspect",
    page_icon="📊",
    layout="wide"
)


def count_work_days(start_date: datetime, end_date: datetime) -> int:
    """Count work days (Mon-Fri) in date range."""
    work_days = 0
    current = start_date
    while current <= end_date:
        # Monday=0, Friday=4
        if current.weekday() in [0, 1, 2, 3, 4]:
            work_days += 1
        current += timedelta(days=1)
    return work_days


def generate_date_range(start_date: datetime, end_date: datetime) -> List[datetime]:
    """Generate list of all dates in range (inclusive)."""
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def get_daily_calls(repo: Repository, segment: str, date_from: datetime,
                    date_to: datetime, stage_filter: Optional[str] = None) -> List[Dict]:
    """Get total calls per day for a segment."""

    # Build query
    query = """
        SELECT
            DATE(c.call_date) as call_day,
            COUNT(*) as total_calls
        FROM calls c
        JOIN accounts a ON c.account_id = a.id
        WHERE a.primary_segment = ?
          AND c.call_date >= ?
          AND c.call_date <= ?
    """
    params = [segment, date_from.isoformat(), date_to.isoformat()]

    if stage_filter and stage_filter != "all":
        query += " AND c.primary_stage = ?"
        params.append(stage_filter)

    query += """
        GROUP BY DATE(c.call_date)
        ORDER BY call_day
    """

    # Execute query
    cursor = repo.conn.execute(query, params)
    results = cursor.fetchall()

    # Fill in missing dates with 0 (including weekends)
    date_range = generate_date_range(date_from, date_to)
    data_points = []

    results_dict = {row['call_day']: row['total_calls'] for row in results}

    for dt in date_range:
        date_str = dt.strftime('%Y-%m-%d')
        data_points.append({
            'date': dt,
            'date_label': dt.strftime('%b %d'),
            'value': results_dict.get(date_str, 0)
        })

    return data_points


def get_daily_unique_accounts(repo: Repository, segment: str, date_from: datetime,
                               date_to: datetime, stage_filter: Optional[str] = None) -> List[Dict]:
    """Get unique accounts engaged per day for a segment."""

    # Build query
    query = """
        SELECT
            DATE(c.call_date) as call_day,
            COUNT(DISTINCT c.account_id) as unique_accounts
        FROM calls c
        JOIN accounts a ON c.account_id = a.id
        WHERE a.primary_segment = ?
          AND c.call_date >= ?
          AND c.call_date <= ?
    """
    params = [segment, date_from.isoformat(), date_to.isoformat()]

    if stage_filter and stage_filter != "all":
        query += " AND c.primary_stage = ?"
        params.append(stage_filter)

    query += """
        GROUP BY DATE(c.call_date)
        ORDER BY call_day
    """

    # Execute query
    cursor = repo.conn.execute(query, params)
    results = cursor.fetchall()

    # Fill in missing dates with 0 (including weekends)
    date_range = generate_date_range(date_from, date_to)
    data_points = []

    results_dict = {row['call_day']: row['unique_accounts'] for row in results}

    for dt in date_range:
        date_str = dt.strftime('%Y-%m-%d')
        data_points.append({
            'date': dt,
            'date_label': dt.strftime('%b %d'),
            'value': results_dict.get(date_str, 0)
        })

    return data_points


def get_calls_by_rep(repo: Repository, segment: str, date_from: datetime,
                     date_to: datetime, stage_filter: Optional[str] = None) -> List[Dict]:
    """Get total calls per rep for a segment."""

    # Build query
    query = """
        SELECT
            c.sales_rep_email as rep_email,
            COUNT(*) as total_calls
        FROM calls c
        JOIN accounts a ON c.account_id = a.id
        WHERE a.primary_segment = ?
          AND c.call_date >= ?
          AND c.call_date <= ?
    """
    params = [segment, date_from.isoformat(), date_to.isoformat()]

    if stage_filter and stage_filter != "all":
        query += " AND c.primary_stage = ?"
        params.append(stage_filter)

    query += """
        GROUP BY c.sales_rep_email
        ORDER BY total_calls DESC
    """

    # Execute query
    cursor = repo.conn.execute(query, params)
    results = cursor.fetchall()

    data_points = []
    for row in results:
        # Extract name from email (before @)
        rep_name = row['rep_email'].split('@')[0] if row['rep_email'] else 'Unknown'
        data_points.append({
            'rep_email': row['rep_email'],
            'rep_name': rep_name,
            'value': row['total_calls']
        })

    return data_points


def get_accounts_by_rep(repo: Repository, segment: str, date_from: datetime,
                        date_to: datetime, stage_filter: Optional[str] = None) -> List[Dict]:
    """Get unique accounts per rep for a segment."""

    # Build query
    query = """
        SELECT
            c.sales_rep_email as rep_email,
            COUNT(DISTINCT c.account_id) as unique_accounts
        FROM calls c
        JOIN accounts a ON c.account_id = a.id
        WHERE a.primary_segment = ?
          AND c.call_date >= ?
          AND c.call_date <= ?
    """
    params = [segment, date_from.isoformat(), date_to.isoformat()]

    if stage_filter and stage_filter != "all":
        query += " AND c.primary_stage = ?"
        params.append(stage_filter)

    query += """
        GROUP BY c.sales_rep_email
        ORDER BY unique_accounts DESC
    """

    # Execute query
    cursor = repo.conn.execute(query, params)
    results = cursor.fetchall()

    data_points = []
    for row in results:
        # Extract name from email (before @)
        rep_name = row['rep_email'].split('@')[0] if row['rep_email'] else 'Unknown'
        data_points.append({
            'rep_email': row['rep_email'],
            'rep_name': rep_name,
            'value': row['unique_accounts']
        })

    return data_points


def calculate_panel_metrics(repo: Repository, segment: str, date_from: datetime,
                            date_to: datetime, stage_filter: Optional[str] = None) -> Dict:
    """Calculate all metrics for a panel."""

    # Build query for calls with filters
    query_parts = ["""
        SELECT c.*, a.primary_segment
        FROM calls c
        JOIN accounts a ON c.account_id = a.id
        WHERE a.primary_segment = ?
    """]
    params = [segment]

    # Date range filter
    if date_from:
        query_parts.append("AND c.call_date >= ?")
        params.append(date_from.isoformat())
    if date_to:
        query_parts.append("AND c.call_date <= ?")
        params.append(date_to.isoformat())

    # Stage filter
    if stage_filter and stage_filter != "all":
        query_parts.append("AND c.primary_stage = ?")
        params.append(stage_filter)

    query = " ".join(query_parts)
    cursor = repo.conn.execute(query, params)
    segment_calls = cursor.fetchall()

    # Get unique account IDs
    segment_account_ids = set(call['account_id'] for call in segment_calls)

    # Get rep count for this segment
    all_reps = repo.list_sales_reps(active_only=True)
    segment_reps = [r for r in all_reps if r.segment == segment]
    rep_count = len(segment_reps)

    # Calculate metrics
    total_calls = len(segment_calls)
    unique_accounts = len(segment_account_ids)

    # Calculate work days in period
    work_days = count_work_days(date_from, date_to)

    # Avg calls per rep per day
    calls_per_rep_per_day = 0
    if rep_count > 0 and work_days > 0:
        calls_per_rep_per_day = total_calls / (rep_count * work_days)

    # Avg accounts per rep
    accounts_per_rep = 0
    if rep_count > 0:
        accounts_per_rep = unique_accounts / rep_count

    return {
        "total_calls": total_calls,
        "unique_accounts": unique_accounts,
        "rep_count": rep_count,
        "calls_per_rep_per_day": calls_per_rep_per_day,
        "accounts_per_rep": accounts_per_rep,
    }


def create_bar_chart(data_points: List[Dict], title: str, color: str,
                     value_suffix: str = "") -> go.Figure:
    """Create a daily bar chart with shadow border styling."""

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=[d['date_label'] for d in data_points],
        y=[d['value'] for d in data_points],
        marker_color=color,
        hovertemplate='%{x}<br>%{y}' + value_suffix + '<extra></extra>'
    ))

    # Determine x-axis tick frequency based on data length
    num_points = len(data_points)
    if num_points <= 7:
        dtick = 1  # Show all dates
    elif num_points <= 30:
        dtick = 3  # Show every 3 days
    else:
        dtick = 7  # Show every 7 days

    fig.update_layout(
        title=dict(text=title, font=dict(size=16, weight=600)),
        xaxis=dict(
            title="",
            tickangle=-45,
            dtick=dtick,
            gridcolor='#f1f5f9',
            showline=True,
            linewidth=1,
            linecolor='#e2e8f0',
        ),
        yaxis=dict(
            title="",
            gridcolor='#f1f5f9',
            rangemode='tozero',
            showline=True,
            linewidth=1,
            linecolor='#e2e8f0',
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(l=40, r=20, t=50, b=60),
        height=280,
        showlegend=False,
    )

    return fig


def create_categorical_bar_chart(data_points: List[Dict], title: str, color: str,
                                  value_suffix: str = "", x_field: str = 'rep_name') -> go.Figure:
    """Create a categorical bar chart (e.g., by rep) with shadow border styling."""

    if not data_points:
        # Return empty chart if no data
        fig = go.Figure()
        fig.update_layout(
            title=dict(text=title, font=dict(size=16, weight=600)),
            annotations=[dict(text="No data available", showarrow=False,
                            xref="paper", yref="paper", x=0.5, y=0.5)]
        )
        return fig

    # Limit to top 10 if more than 10 items
    display_data = data_points[:10] if len(data_points) > 10 else data_points

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=[d[x_field] for d in display_data],
        y=[d['value'] for d in display_data],
        marker_color=color,
        hovertemplate='%{x}<br>%{y}' + value_suffix + '<extra></extra>'
    ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=16, weight=600)),
        xaxis=dict(
            title="",
            tickangle=-45,
            gridcolor='#f1f5f9',
            showline=True,
            linewidth=1,
            linecolor='#e2e8f0',
        ),
        yaxis=dict(
            title="",
            gridcolor='#f1f5f9',
            rangemode='tozero',
            showline=True,
            linewidth=1,
            linecolor='#e2e8f0',
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(l=40, r=20, t=50, b=80),
        height=280,
        showlegend=False,
    )

    return fig


def render_metric_card(label: str, value: str, key: str):
    """Render a metric using shadcn-ui card component."""
    if SHADCN_AVAILABLE:
        try:
            ui.metric_card(
                title=label,
                content=value,
                description="",
                key=key
            )
        except:
            # Fallback to custom styled metric
            st.markdown(
                f"""
                <div style="
                    background: white;
                    padding: 24px;
                    border-radius: 8px;
                    border: 1px solid #e2e8f0;
                    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
                ">
                    <div style="color: #64748b; font-size: 14px; font-weight: 500; margin-bottom: 8px;">
                        {label}
                    </div>
                    <div style="color: #0f172a; font-size: 36px; font-weight: 600;">
                        {value}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        # Fallback with custom styling
        st.markdown(
            f"""
            <div style="
                background: white;
                padding: 24px;
                border-radius: 8px;
                border: 1px solid #e2e8f0;
                box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
            ">
                <div style="color: #64748b; font-size: 14px; font-weight: 500; margin-bottom: 8px;">
                    {label}
                </div>
                <div style="color: #0f172a; font-size: 36px; font-weight: 600;">
                    {value}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


def render_panel(repo: Repository, panel_id: str, segment: str,
                 date_from: datetime, date_to: datetime,
                 stage_filter: Optional[str] = None):
    """Render a single panel with KPIs and charts."""

    # Calculate metrics
    metrics = calculate_panel_metrics(repo, segment, date_from, date_to, stage_filter)

    # Display KPIs
    st.markdown(f"### {segment.title()}")
    st.markdown("")

    # Row 1: Total Calls and Calls/Rep/Day
    col1, col2 = st.columns(2)

    with col1:
        render_metric_card(
            "Total Calls",
            str(metrics['total_calls']),
            f"metric_calls_{panel_id}"
        )

    with col2:
        render_metric_card(
            "Calls/Rep/Day",
            f"{metrics['calls_per_rep_per_day']:.1f}",
            f"metric_calls_per_rep_{panel_id}"
        )

    st.markdown("")

    # Row 2: Unique Accounts and Accounts/Rep
    col3, col4 = st.columns(2)

    with col3:
        render_metric_card(
            "Unique Accounts",
            str(metrics['unique_accounts']),
            f"metric_accounts_{panel_id}"
        )

    with col4:
        render_metric_card(
            "Accounts/Rep",
            f"{metrics['accounts_per_rep']:.1f}",
            f"metric_accounts_per_rep_{panel_id}"
        )

    st.markdown("")

    # Row 3: Sales Reps
    col5, col6 = st.columns([1, 1])

    with col5:
        render_metric_card(
            "Sales Reps",
            str(metrics['rep_count']),
            f"metric_reps_{panel_id}"
        )

    st.markdown("")
    st.markdown("---")
    st.markdown("")

    # Chart 1: Total Calls Per Day
    daily_calls = get_daily_calls(repo, segment, date_from, date_to, stage_filter)
    fig_calls = create_bar_chart(
        daily_calls,
        "Total Calls Per Day",
        "#3498db",
        " calls"
    )

    with st.container():
        st.plotly_chart(fig_calls, use_container_width=True, key=f"chart_calls_{panel_id}")

    st.markdown("")

    # Chart 2: Distribution of Calls by Rep
    calls_by_rep = get_calls_by_rep(repo, segment, date_from, date_to, stage_filter)
    fig_calls_by_rep = create_categorical_bar_chart(
        calls_by_rep,
        "Distribution of Calls by Rep",
        "#3498db",
        " calls"
    )

    with st.container():
        st.plotly_chart(fig_calls_by_rep, use_container_width=True, key=f"chart_calls_by_rep_{panel_id}")

    st.markdown("")

    # Chart 3: Unique Accounts Per Day
    daily_accounts = get_daily_unique_accounts(repo, segment, date_from, date_to, stage_filter)
    fig_accounts = create_bar_chart(
        daily_accounts,
        "Unique Accounts Per Day",
        "#27ae60",
        " accounts"
    )

    with st.container():
        st.plotly_chart(fig_accounts, use_container_width=True, key=f"chart_accounts_{panel_id}")

    st.markdown("")

    # Chart 4: Distribution of Unique Accounts by Rep
    accounts_by_rep = get_accounts_by_rep(repo, segment, date_from, date_to, stage_filter)
    fig_accounts_by_rep = create_categorical_bar_chart(
        accounts_by_rep,
        "Distribution of Unique Accounts by Rep",
        "#27ae60",
        " accounts"
    )

    with st.container():
        st.plotly_chart(fig_accounts_by_rep, use_container_width=True, key=f"chart_accounts_by_rep_{panel_id}")


def main():
    """Main Summary dashboard."""

    # Load Font Awesome
    st.markdown("""
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    """, unsafe_allow_html=True)

    st.markdown('<h1 style="margin-bottom: 0;"><i class="fas fa-chart-line" style="color: #3498db;"></i> Summary</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color: #7f8c8d; margin-top: 0; margin-bottom: 1rem;">Sales activity and engagement overview</p>', unsafe_allow_html=True)
    st.markdown("---")

    # Load database connection
    config = Config()
    db = Database(config.SQLITE_DB_PATH)
    db.connect()
    repo = Repository(db.conn)

    try:
        # Get available segments from sales_reps table
        all_reps = repo.list_sales_reps(active_only=True)
        available_segments = sorted(list(set(r.segment for r in all_reps)))
        segment_display_map = {seg: seg.title() for seg in available_segments}

        # === SIDEBAR FILTERS ===
        st.sidebar.header("⚙️ Filters")
        st.sidebar.markdown("")

        # Date Range
        date_options = {
            "Last 7 days": 7,
            "Last 30 days": 30,
            "Last 90 days": 90,
        }

        date_selection = st.sidebar.radio(
            "Date Range",
            options=list(date_options.keys()),
            index=1  # Default to last 30 days
        )

        days = date_options[date_selection]
        date_from = datetime.now() - timedelta(days=days)
        date_to = datetime.now()

        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**Period:** {date_from.strftime('%b %d, %Y')} - {date_to.strftime('%b %d, %Y')}")
        st.sidebar.markdown(f"**Days:** {days}")
        st.sidebar.markdown(f"**Work Days:** {count_work_days(date_from, date_to)}")

        # === MAIN CONTENT ===

        # Two-panel layout
        col_left, col_right = st.columns(2)

        with col_left:
            # Segment selector for Panel 1
            segment1 = st.selectbox(
                "Select Segment",
                options=available_segments,
                format_func=lambda x: segment_display_map[x],
                index=0 if "enterprise" in available_segments else 0,
                key="segment_panel1"
            )

            st.markdown("")

            # Render Panel 1
            render_panel(repo, "panel1", segment1, date_from, date_to)

        with col_right:
            # Segment selector for Panel 2
            segment2 = st.selectbox(
                "Select Segment",
                options=available_segments,
                format_func=lambda x: segment_display_map[x],
                index=1 if len(available_segments) > 1 else 0,
                key="segment_panel2"
            )

            st.markdown("")

            # Render Panel 2
            render_panel(repo, "panel2", segment2, date_from, date_to)

    finally:
        db.close()


if __name__ == "__main__":
    main()
