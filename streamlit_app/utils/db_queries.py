"""Database query functions for the Streamlit UI.

This module provides functions to query and filter data from the SQLite database.
All functions work with the JSON-based schema in accounts table.
"""

import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path to import from src/
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.models import AccountCall, AccountRecord
from src.sqlite_repository import SQLiteCallRepository


async def get_all_accounts_filtered(
    repository: SQLiteCallRepository,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    min_calls: Optional[int] = None,
    max_score: Optional[float] = None
) -> List[AccountRecord]:
    """
    Get all accounts with optional filters applied in Python.

    Args:
        repository: SQLiteCallRepository instance
        date_from: Filter calls on/after this date (naive datetime will be treated as local)
        date_to: Filter calls on/before this date (naive datetime will be treated as local)
        min_calls: Only return accounts with at least this many calls
        max_score: Only return accounts with score <= this value

    Returns:
        List[AccountRecord] with filtered calls

    Note: Date filtering is applied to calls within each account,
          but account is included if it has at least one call in range.
    """
    # Get all accounts from DB
    all_accounts = await repository.get_all_accounts()

    filtered_accounts = []
    for account in all_accounts:
        # Filter calls by date range
        filtered_calls = account.calls
        if date_from:
            # Make date comparison work with both naive and aware datetimes
            # by comparing dates only (ignore timezone)
            filtered_calls = [
                c for c in filtered_calls
                if c.call_date.replace(tzinfo=None) >= date_from.replace(tzinfo=None)
            ]
        if date_to:
            filtered_calls = [
                c for c in filtered_calls
                if c.call_date.replace(tzinfo=None) <= date_to.replace(tzinfo=None)
            ]

        # Skip if no calls in date range
        if not filtered_calls:
            continue

        # Apply min_calls filter
        if min_calls and len(filtered_calls) < min_calls:
            continue

        # Apply max_score filter (use original overall score, not recalculated)
        if max_score and account.overall_meddpicc.overall_score > max_score:
            continue

        # Create filtered account (with recalculated overall_meddpicc if date filtered)
        if date_from or date_to:
            # Recalculate overall MEDDPICC from filtered calls
            filtered_account = AccountRecord(
                domain=account.domain,
                created_at=account.created_at,
                updated_at=account.updated_at,
                calls=filtered_calls,
                overall_meddpicc=repository._calculate_overall_meddpicc(filtered_calls)
            )
            filtered_accounts.append(filtered_account)
        else:
            # Use original account (no recalculation needed)
            filtered_accounts.append(account)

    return filtered_accounts


def get_calls_by_rep(
    accounts: List[AccountRecord],
    rep_email: str
) -> List[AccountCall]:
    """
    Extract all calls for a specific sales rep from accounts.

    Args:
        accounts: List of AccountRecord objects
        rep_email: Sales rep email to filter by

    Returns:
        List[AccountCall] for this rep, sorted by date descending
    """
    rep_calls = []
    for account in accounts:
        rep_calls.extend([
            call for call in account.calls
            if call.sales_rep == rep_email
        ])

    # Sort by date, most recent first
    rep_calls.sort(key=lambda c: c.call_date, reverse=True)
    return rep_calls


def get_all_reps(accounts: List[AccountRecord]) -> List[str]:
    """
    Get list of all unique sales rep emails from accounts.

    Args:
        accounts: List of AccountRecord objects

    Returns:
        List of unique rep emails, sorted alphabetically
    """
    all_reps = set()
    for account in accounts:
        for call in account.calls:
            all_reps.add(call.sales_rep)

    return sorted(list(all_reps))


def get_team_stats(accounts: List[AccountRecord]) -> Dict[str, Any]:
    """
    Calculate team-wide statistics from accounts.

    Args:
        accounts: List of AccountRecord objects

    Returns:
        Dict with team statistics:
        - total_discovery_calls: int
        - unique_reps: int
        - unique_accounts: int
        - avg_overall_score: float
        - avg_scores_by_dimension: Dict[str, float]
    """
    # Collect all calls
    all_calls = []
    all_reps = set()

    for account in accounts:
        all_calls.extend(account.calls)
        for call in account.calls:
            all_reps.add(call.sales_rep)

    if not all_calls:
        return {
            'total_discovery_calls': 0,
            'unique_reps': 0,
            'unique_accounts': 0,
            'avg_overall_score': 0.0,
            'avg_scores_by_dimension': {}
        }

    # Calculate averages
    dimensions = ['metrics', 'economic_buyer', 'decision_criteria',
                  'decision_process', 'paper_process', 'identify_pain',
                  'champion', 'competition']

    avg_scores = {}
    for dim in dimensions:
        scores = [getattr(call.meddpicc_scores, dim) for call in all_calls]
        avg_scores[dim] = sum(scores) / len(scores)

    overall_scores = [call.meddpicc_scores.overall_score for call in all_calls]

    return {
        'total_discovery_calls': len(all_calls),
        'unique_reps': len(all_reps),
        'unique_accounts': len(accounts),
        'avg_overall_score': sum(overall_scores) / len(overall_scores),
        'avg_scores_by_dimension': avg_scores
    }


def get_rep_comparison(accounts: List[AccountRecord]) -> List[Dict[str, Any]]:
    """
    Get per-rep statistics for comparison.

    Args:
        accounts: List of AccountRecord objects

    Returns:
        List[Dict] with one entry per rep:
        - rep_email: str
        - total_calls: int
        - avg_overall_score: float
        - avg_scores_by_dimension: Dict[str, float]
    """
    # Group calls by rep
    calls_by_rep = {}
    for account in accounts:
        for call in account.calls:
            if call.sales_rep not in calls_by_rep:
                calls_by_rep[call.sales_rep] = []
            calls_by_rep[call.sales_rep].append(call)

    # Calculate stats per rep
    rep_stats = []
    dimensions = ['metrics', 'economic_buyer', 'decision_criteria',
                  'decision_process', 'paper_process', 'identify_pain',
                  'champion', 'competition']

    for rep_email, calls in calls_by_rep.items():
        # Calculate dimension averages
        avg_scores = {}
        for dim in dimensions:
            scores = [getattr(call.meddpicc_scores, dim) for call in calls]
            avg_scores[dim] = sum(scores) / len(scores)

        # Overall average
        overall_scores = [call.meddpicc_scores.overall_score for call in calls]
        avg_overall = sum(overall_scores) / len(overall_scores)

        rep_stats.append({
            'rep_email': rep_email,
            'total_calls': len(calls),
            'avg_overall_score': avg_overall,
            'avg_scores_by_dimension': avg_scores
        })

    # Sort by overall score descending
    rep_stats.sort(key=lambda r: r['avg_overall_score'], reverse=True)
    return rep_stats


def get_time_series(
    accounts: List[AccountRecord],
    group_by: str = 'week'
) -> List[Dict[str, Any]]:
    """
    Get time series data grouped by period.

    Args:
        accounts: List of AccountRecord objects
        group_by: 'day', 'week', or 'month'

    Returns:
        List[Dict] with one entry per period:
        - period: str (e.g., "2026-W03" for week, "2026-01-15" for day)
        - total_calls: int
        - avg_overall_score: float
        - avg_scores_by_dimension: Dict[str, float]
    """
    # Collect all calls
    all_calls = []
    for account in accounts:
        all_calls.extend(account.calls)

    # Group calls by period
    calls_by_period = defaultdict(list)

    for call in all_calls:
        if group_by == 'day':
            period = call.call_date.strftime('%Y-%m-%d')
        elif group_by == 'week':
            period = call.call_date.strftime('%Y-W%U')
        elif group_by == 'month':
            period = call.call_date.strftime('%Y-%m')
        else:
            raise ValueError(f"Invalid group_by: {group_by}")

        calls_by_period[period].append(call)

    # Calculate stats per period
    dimensions = ['metrics', 'economic_buyer', 'decision_criteria',
                  'decision_process', 'paper_process', 'identify_pain',
                  'champion', 'competition']

    time_series = []
    for period, calls in sorted(calls_by_period.items()):
        # Calculate dimension averages
        avg_scores = {}
        for dim in dimensions:
            scores = [getattr(call.meddpicc_scores, dim) for call in calls]
            avg_scores[dim] = sum(scores) / len(scores)

        # Overall average
        overall_scores = [call.meddpicc_scores.overall_score for call in calls]

        time_series.append({
            'period': period,
            'total_calls': len(calls),
            'avg_overall_score': sum(overall_scores) / len(overall_scores),
            'avg_scores_by_dimension': avg_scores
        })

    return time_series


async def get_evaluated_calls_stats(
    repository: SQLiteCallRepository
) -> Dict[str, Any]:
    """
    Get statistics from evaluated_calls table.

    Args:
        repository: SQLiteCallRepository instance

    Returns:
        Dict with:
        - total_evaluated: int
        - total_discovery: int
        - total_non_discovery: int
        - discovery_rate: float (0-100)
        - rejection_reasons: List[Tuple[str, int]] (reason, count)
    """
    cursor = repository.conn.execute(
        "SELECT is_discovery, reason FROM evaluated_calls"
    )

    results = cursor.fetchall()

    if not results:
        return {
            'total_evaluated': 0,
            'total_discovery': 0,
            'total_non_discovery': 0,
            'discovery_rate': 0.0,
            'rejection_reasons': []
        }

    discovery_count = sum(1 for r in results if r[0] == 1)
    non_discovery_count = sum(1 for r in results if r[0] == 0)

    # Count rejection reasons
    reasons = [r[1] for r in results if r[0] == 0 and r[1]]
    reason_counts = Counter(reasons).most_common()

    return {
        'total_evaluated': len(results),
        'total_discovery': discovery_count,
        'total_non_discovery': non_discovery_count,
        'discovery_rate': (discovery_count / len(results)) * 100 if results else 0.0,
        'rejection_reasons': reason_counts
    }


def get_account_red_flags(
    accounts: List[AccountRecord],
    min_calls: int = 3,
    max_score: float = 3.0
) -> List[AccountRecord]:
    """
    Get accounts that are red flags (weak after multiple calls).

    Args:
        accounts: List of AccountRecord objects
        min_calls: Minimum calls to be considered
        max_score: Maximum score to be considered weak

    Returns:
        List[AccountRecord] that are red flags, sorted by score ascending
    """
    red_flags = []
    for account in accounts:
        if (len(account.calls) >= min_calls and
            account.overall_meddpicc.overall_score <= max_score):
            red_flags.append(account)

    # Sort by score (lowest first)
    red_flags.sort(key=lambda a: a.overall_meddpicc.overall_score)
    return red_flags


def get_strong_accounts(
    accounts: List[AccountRecord],
    min_score: float = 4.0
) -> List[AccountRecord]:
    """
    Get accounts with strong qualification.

    Args:
        accounts: List of AccountRecord objects
        min_score: Minimum score to be considered strong

    Returns:
        List[AccountRecord] with strong scores, sorted by score descending
    """
    strong = [a for a in accounts if a.overall_meddpicc.overall_score >= min_score]
    strong.sort(key=lambda a: a.overall_meddpicc.overall_score, reverse=True)
    return strong


def get_moderate_accounts(
    accounts: List[AccountRecord],
    min_score: float = 2.5,
    max_score: float = 4.0
) -> List[AccountRecord]:
    """
    Get accounts with moderate qualification.

    Args:
        accounts: List of AccountRecord objects
        min_score: Minimum score
        max_score: Maximum score

    Returns:
        List[AccountRecord] with moderate scores, sorted by score descending
    """
    moderate = [
        a for a in accounts
        if min_score <= a.overall_meddpicc.overall_score < max_score
    ]
    moderate.sort(key=lambda a: a.overall_meddpicc.overall_score, reverse=True)
    return moderate
