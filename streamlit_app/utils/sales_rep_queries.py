"""Sales rep queries and utilities."""

from typing import Dict, List, Optional
from datetime import datetime

from src.sqlite_repository import SQLiteCallRepository


async def get_all_sales_reps(repo: SQLiteCallRepository) -> List[Dict]:
    """
    Get all sales reps from database.

    Returns:
        List of dicts with keys: email, segment, joining_date, days_tenure
    """
    cursor = repo.conn.execute(
        """
        SELECT
            email,
            segment,
            joining_date,
            julianday('now') - julianday(joining_date) as days_tenure
        FROM sales_reps
        ORDER BY segment, joining_date
        """
    )

    reps = []
    for row in cursor.fetchall():
        email, segment, joining_date_str, days_tenure = row
        reps.append({
            'email': email,
            'segment': segment,
            'joining_date': datetime.fromisoformat(joining_date_str),
            'days_tenure': int(days_tenure) if days_tenure else 0
        })

    return reps


async def get_sales_rep(repo: SQLiteCallRepository, email: str) -> Optional[Dict]:
    """
    Get a single sales rep by email.

    Returns:
        Dict with keys: email, segment, joining_date, days_tenure, or None if not found
    """
    cursor = repo.conn.execute(
        """
        SELECT
            email,
            segment,
            joining_date,
            julianday('now') - julianday(joining_date) as days_tenure
        FROM sales_reps
        WHERE email = ?
        """,
        (email,)
    )

    row = cursor.fetchone()
    if not row:
        return None

    email, segment, joining_date_str, days_tenure = row
    return {
        'email': email,
        'segment': segment,
        'joining_date': datetime.fromisoformat(joining_date_str),
        'days_tenure': int(days_tenure) if days_tenure else 0
    }


async def get_segments(repo: SQLiteCallRepository) -> List[str]:
    """
    Get all unique segments from sales_reps table.

    Returns:
        List of segment names, sorted
    """
    cursor = repo.conn.execute(
        """
        SELECT DISTINCT segment
        FROM sales_reps
        ORDER BY segment
        """
    )

    return [row[0] for row in cursor.fetchall()]


def get_rep_segment_map(sales_reps: List[Dict]) -> Dict[str, str]:
    """
    Create a map of rep email to segment.

    Args:
        sales_reps: List of rep dicts from get_all_sales_reps()

    Returns:
        Dict mapping email -> segment
    """
    return {rep['email']: rep['segment'] for rep in sales_reps}


def filter_accounts_by_segment(accounts, segment: str, rep_segment_map: Dict[str, str]):
    """
    Filter accounts to only those with calls from reps in the specified segment.

    Args:
        accounts: List of AccountRecord objects
        segment: Segment to filter by (e.g., "enterprise")
        rep_segment_map: Dict mapping rep email -> segment

    Returns:
        Filtered list of accounts
    """
    if segment.lower() == "all segments":
        return accounts

    filtered = []
    for account in accounts:
        # Check if any call in this account is from a rep in the target segment
        has_segment_call = any(
            rep_segment_map.get(call.sales_rep) == segment
            for call in account.calls
        )
        if has_segment_call:
            filtered.append(account)

    return filtered


def filter_calls_by_segment(calls, segment: str, rep_segment_map: Dict[str, str]):
    """
    Filter calls to only those from reps in the specified segment.

    Args:
        calls: List of AccountCall objects
        segment: Segment to filter by
        rep_segment_map: Dict mapping rep email -> segment

    Returns:
        Filtered list of calls
    """
    if segment.lower() == "all segments":
        return calls

    return [
        call for call in calls
        if rep_segment_map.get(call.sales_rep) == segment
    ]
