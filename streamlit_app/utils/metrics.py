"""Metrics and insights calculations for coaching."""

from typing import Any, Dict, List, Optional, Tuple

from src.models import AccountCall, AccountRecord

from .styling import MEDDPICC_DIMENSIONS


def detect_account_red_flags(account: AccountRecord) -> List[str]:
    """
    Detect red flags for an account.

    Args:
        account: AccountRecord to analyze

    Returns:
        List of red flag descriptions
    """
    flags = []

    # Multiple calls but weak qualification
    if len(account.calls) >= 3 and account.overall_meddpicc.overall_score < 3.0:
        flags.append(f"Weak qualification after {len(account.calls)} calls")

    # No economic buyer access
    if len(account.calls) >= 2 and account.overall_meddpicc.economic_buyer < 3:
        flags.append(f"No economic buyer access after {len(account.calls)} calls")

    # Critical dimension at 0
    critical_dims = {
        'economic_buyer': 'Economic Buyer',
        'champion': 'Champion',
        'identify_pain': 'Pain'
    }
    for dim_key, dim_name in critical_dims.items():
        if getattr(account.overall_meddpicc, dim_key) == 0:
            flags.append(f"No {dim_name} identified")

    return flags


def get_dimension_gaps(
    account: AccountRecord,
    threshold: float = 4.0
) -> List[Tuple[str, int, str]]:
    """
    Get dimensions that need improvement for an account.

    Args:
        account: AccountRecord to analyze
        threshold: Score below this is considered a gap

    Returns:
        List of (dimension_key, score, dimension_name) tuples
    """
    gaps = []

    for dim in MEDDPICC_DIMENSIONS:
        score = getattr(account.overall_meddpicc, dim)
        if score < threshold:
            from .styling import format_dimension_name
            dim_name = format_dimension_name(dim)
            gaps.append((dim, score, dim_name))

    # Sort by score (lowest first)
    gaps.sort(key=lambda x: x[1])
    return gaps


def generate_coaching_priorities(
    team_stats: Dict[str, Any],
    top_n: int = 3
) -> List[Dict[str, Any]]:
    """
    Generate top coaching priorities based on team statistics.

    Args:
        team_stats: Team statistics from get_team_stats()
        top_n: Number of priorities to return

    Returns:
        List of coaching priority dicts with:
        - dimension: str (dimension key)
        - dimension_name: str (display name)
        - score: float (average score)
        - severity: str ("critical" | "needs_work" | "moderate")
        - observation: str (what's happening)
    """
    from .styling import format_dimension_name

    if not team_stats or not team_stats.get('avg_scores_by_dimension'):
        return []

    avg_scores = team_stats['avg_scores_by_dimension']

    # Create priority list
    priorities = []
    for dim in MEDDPICC_DIMENSIONS:
        score = avg_scores.get(dim, 0)

        # Determine severity
        if score < 2.5:
            severity = "critical"
        elif score < 3.5:
            severity = "needs_work"
        else:
            severity = "moderate"

        # Generate observation
        observation = generate_dimension_observation(
            dim,
            score,
            team_stats['total_discovery_calls']
        )

        priorities.append({
            'dimension': dim,
            'dimension_name': format_dimension_name(dim),
            'score': score,
            'severity': severity,
            'observation': observation
        })

    # Sort by score (lowest first) and return top N
    priorities.sort(key=lambda p: p['score'])
    return priorities[:top_n]


def generate_dimension_observation(
    dimension: str,
    score: float,
    total_calls: int
) -> str:
    """
    Generate observation text for a dimension.

    Args:
        dimension: Dimension key
        score: Average score
        total_calls: Total number of calls

    Returns:
        Observation text
    """
    # Calculate percentage of calls with low scores (0-2)
    # This is an approximation based on average
    if score < 2.0:
        low_pct = "85-95%"
    elif score < 2.5:
        low_pct = "70-85%"
    elif score < 3.0:
        low_pct = "50-70%"
    else:
        low_pct = "30-50%"

    observations = {
        'metrics': f"~{low_pct} of calls lack quantifiable business outcomes or ROI targets",
        'economic_buyer': f"~{low_pct} of calls missing C-level or budget authority engagement",
        'decision_criteria': f"~{low_pct} of calls don't uncover formal evaluation criteria",
        'decision_process': f"~{low_pct} of calls lack clarity on decision steps and timeline",
        'paper_process': f"~{low_pct} of calls don't discuss legal/procurement process",
        'identify_pain': f"~{low_pct} of calls have weak or missing pain discovery",
        'champion': f"~{low_pct} of calls lack identification of an internal advocate",
        'competition': f"~{low_pct} of calls don't explore competitive landscape"
    }

    return observations.get(dimension, f"Average score of {score:.1f}")


def get_rep_strengths_and_weaknesses(
    rep_scores: Dict[str, float],
    team_scores: Dict[str, float],
    top_n: int = 3
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Identify rep's strengths and weaknesses vs team.

    Args:
        rep_scores: Rep's average scores by dimension
        team_scores: Team average scores by dimension
        top_n: Number of strengths/weaknesses to return

    Returns:
        Tuple of (strengths, weaknesses) lists
    """
    from .styling import format_dimension_name

    comparisons = []

    for dim in MEDDPICC_DIMENSIONS:
        rep_score = rep_scores.get(dim, 0)
        team_score = team_scores.get(dim, 0)
        delta = rep_score - team_score

        comparisons.append({
            'dimension': dim,
            'dimension_name': format_dimension_name(dim),
            'rep_score': rep_score,
            'team_score': team_score,
            'delta': delta
        })

    # Strengths: Significantly above team (delta > 0.3)
    strengths = [c for c in comparisons if c['delta'] > 0.3]
    strengths.sort(key=lambda x: x['delta'], reverse=True)

    # Weaknesses: Below team or low score
    weaknesses = [
        c for c in comparisons
        if c['delta'] < 0 or c['rep_score'] < 3.0
    ]
    weaknesses.sort(key=lambda x: (x['rep_score'], x['delta']))

    return strengths[:top_n], weaknesses[:top_n]


def calculate_score_improvement(
    calls: List[AccountCall],
    dimension: Optional[str] = None
) -> float:
    """
    Calculate improvement between first and last call.

    Args:
        calls: List of AccountCall objects
        dimension: Specific dimension to measure, or None for overall

    Returns:
        Improvement delta (positive = improved, negative = declined)
    """
    if len(calls) < 2:
        return 0.0

    # Sort by date
    sorted_calls = sorted(calls, key=lambda c: c.call_date)

    if dimension:
        first_score = getattr(sorted_calls[0].meddpicc_scores, dimension)
        last_score = getattr(sorted_calls[-1].meddpicc_scores, dimension)
    else:
        first_score = sorted_calls[0].meddpicc_scores.overall_score
        last_score = sorted_calls[-1].meddpicc_scores.overall_score

    return last_score - first_score


def get_best_example_call(
    calls: List[AccountCall],
    dimension: Optional[str] = None
) -> Optional[AccountCall]:
    """
    Get the best example call for a dimension.

    Args:
        calls: List of AccountCall objects
        dimension: Dimension to find best example for, or None for overall

    Returns:
        Best call, or None if no calls
    """
    if not calls:
        return None

    if dimension:
        # Sort by dimension score
        return max(calls, key=lambda c: getattr(c.meddpicc_scores, dimension))
    else:
        # Sort by overall score
        return max(calls, key=lambda c: c.meddpicc_scores.overall_score)


def get_worst_example_call(
    calls: List[AccountCall],
    dimension: Optional[str] = None
) -> Optional[AccountCall]:
    """
    Get the worst example call for a dimension.

    Args:
        calls: List of AccountCall objects
        dimension: Dimension to find worst example for, or None for overall

    Returns:
        Worst call, or None if no calls
    """
    if not calls:
        return None

    if dimension:
        # Sort by dimension score
        return min(calls, key=lambda c: getattr(c.meddpicc_scores, dimension))
    else:
        # Sort by overall score
        return min(calls, key=lambda c: c.meddpicc_scores.overall_score)


def get_top_calls_in_weak_areas(
    calls: List[AccountCall],
    weak_dimensions: List[str],
    top_n: int = 10
) -> List[AccountCall]:
    """
    Get top calls that performed well in the team's weak dimensions.

    Args:
        calls: List of all calls
        weak_dimensions: List of dimension keys where team is weak
        top_n: Number of calls to return

    Returns:
        List of top calls sorted by their average score in weak dimensions
    """
    if not calls or not weak_dimensions:
        return []

    # Calculate average score in weak dimensions for each call
    call_scores = []
    for call in calls:
        weak_scores = [getattr(call.meddpicc_scores, dim) for dim in weak_dimensions]
        avg_weak_score = sum(weak_scores) / len(weak_scores) if weak_scores else 0
        call_scores.append((call, avg_weak_score))

    # Sort by average score in weak dimensions (descending)
    call_scores.sort(key=lambda x: x[1], reverse=True)

    # Return top N calls
    return [call for call, score in call_scores[:top_n]]


def get_top_accounts_by_discovery(
    accounts: List[AccountRecord],
    top_n: int = 10
) -> List[AccountRecord]:
    """
    Get top accounts with the best overall MEDDPICC discovery.

    Args:
        accounts: List of all accounts
        top_n: Number of accounts to return

    Returns:
        List of top accounts sorted by overall MEDDPICC score
    """
    if not accounts:
        return []

    # Sort by overall score (descending)
    sorted_accounts = sorted(
        accounts,
        key=lambda a: a.overall_meddpicc.overall_score,
        reverse=True
    )

    return sorted_accounts[:top_n]


def generate_next_steps(account: AccountRecord) -> List[str]:
    """
    Generate recommended next steps for an account.

    Args:
        account: AccountRecord to analyze

    Returns:
        List of recommended action items
    """
    next_steps = []

    # Get dimension gaps
    gaps = get_dimension_gaps(account, threshold=4.0)

    for dim, score, dim_name in gaps[:3]:  # Top 3 gaps
        if dim == 'economic_buyer' and score < 3:
            next_steps.append(
                f"Schedule call with economic buyer/budget holder "
                f"(current EB score: {score})"
            )
        elif dim == 'paper_process' and score < 3:
            next_steps.append(
                f"Clarify legal and procurement process "
                f"(current PP score: {score})"
            )
        elif dim == 'champion' and score < 3:
            next_steps.append(
                f"Identify and cultivate an internal champion "
                f"(current CH score: {score})"
            )
        elif dim == 'competition' and score < 3:
            next_steps.append(
                f"Dig deeper into competitive landscape and evaluation criteria "
                f"(current CO score: {score})"
            )
        elif dim == 'metrics' and score < 3:
            next_steps.append(
                f"Establish quantifiable success metrics and ROI targets "
                f"(current M score: {score})"
            )
        elif dim == 'decision_process' and score < 3:
            next_steps.append(
                f"Map out decision timeline and stakeholders "
                f"(current DP score: {score})"
            )
        elif dim == 'decision_criteria' and score < 3:
            next_steps.append(
                f"Uncover formal evaluation criteria "
                f"(current DC score: {score})"
            )
        elif dim == 'identify_pain' and score < 3:
            next_steps.append(
                f"Dig deeper into business pain and impact "
                f"(current IP score: {score})"
            )

    # If strong account, suggest maintaining momentum
    if account.overall_meddpicc.overall_score >= 4.0:
        next_steps.append("✅ Strong qualification - maintain momentum and move to close")

    return next_steps
