"""Styling constants, colors, and formatting functions."""

# Color Palette
COLORS = {
    # Score-based colors
    'score_strong': '#10b981',    # Green
    'score_moderate': '#f59e0b',  # Yellow/Orange
    'score_weak': '#ef4444',      # Red

    # Semantic colors
    'success': '#10b981',
    'warning': '#f59e0b',
    'error': '#ef4444',
    'info': '#3b82f6',

    # Neutral
    'text_primary': '#1f2937',
    'text_secondary': '#6b7280',
    'background': '#ffffff',
    'border': '#e5e7eb',

    # Chart colors (for dimensions)
    'chart_palette': [
        '#3b82f6',  # Blue
        '#8b5cf6',  # Purple
        '#ec4899',  # Pink
        '#f59e0b',  # Orange
        '#10b981',  # Green
        '#06b6d4',  # Cyan
        '#6366f1',  # Indigo
        '#a855f7',  # Violet
    ]
}

# MEDDPICC Dimensions
MEDDPICC_DIMENSIONS = [
    'metrics',
    'economic_buyer',
    'decision_criteria',
    'decision_process',
    'paper_process',
    'identify_pain',
    'champion',
    'competition'
]


def get_score_color(score: float) -> str:
    """
    Return color based on score.

    Args:
        score: Score value (0-5)

    Returns:
        Hex color string
    """
    if score >= 4.0:
        return COLORS['score_strong']
    elif score >= 2.5:
        return COLORS['score_moderate']
    else:
        return COLORS['score_weak']


def get_score_emoji(score: float) -> str:
    """
    Return emoji based on score.

    Args:
        score: Score value (0-5)

    Returns:
        Emoji string
    """
    if score >= 4.0:
        return "🟢"
    elif score >= 2.5:
        return "🟡"
    else:
        return "🔴"


def get_score_label(score: float) -> str:
    """
    Return label based on score.

    Args:
        score: Score value (0-5)

    Returns:
        Label string
    """
    if score >= 4.0:
        return "STRONG"
    elif score >= 2.5:
        return "MODERATE"
    else:
        return "WEAK"


def format_score(score: float) -> str:
    """
    Format score for display.

    Args:
        score: Score value

    Returns:
        Formatted score string (e.g., "3.5")
    """
    return f"{score:.1f}"


def format_delta(delta: float, include_sign: bool = True) -> str:
    """
    Format delta with + or - sign.

    Args:
        delta: Delta value
        include_sign: Whether to include + sign for positive values

    Returns:
        Formatted delta string (e.g., "+0.5", "-0.2")
    """
    if delta > 0 and include_sign:
        return f"+{delta:.1f}"
    else:
        return f"{delta:.1f}"


def format_trend_arrow(delta: float, threshold: float = 0.2) -> str:
    """
    Return trend arrow based on delta.

    Args:
        delta: Change in value
        threshold: Threshold for considering significant change

    Returns:
        Arrow emoji (↗ ↘ →)
    """
    if delta > threshold:
        return "↗"
    elif delta < -threshold:
        return "↘"
    else:
        return "→"


def format_dimension_name(key: str) -> str:
    """
    Convert dimension key to display name.

    Args:
        key: Dimension key (e.g., "economic_buyer")

    Returns:
        Display name (e.g., "Economic Buyer")
    """
    dimension_names = {
        'metrics': 'Metrics',
        'economic_buyer': 'Economic Buyer',
        'decision_criteria': 'Decision Criteria',
        'decision_process': 'Decision Process',
        'paper_process': 'Paper Process',
        'identify_pain': 'Identify Pain',
        'champion': 'Champion',
        'competition': 'Competition',
    }
    return dimension_names.get(key, key.replace('_', ' ').title())


def format_dimension_abbrev(key: str) -> str:
    """
    Convert dimension key to abbreviation.

    Args:
        key: Dimension key (e.g., "economic_buyer")

    Returns:
        Abbreviation (e.g., "E")
    """
    abbrevs = {
        'metrics': 'M',
        'economic_buyer': 'E',
        'decision_criteria': 'DC',
        'decision_process': 'DP',
        'paper_process': 'PP',
        'identify_pain': 'IP',
        'champion': 'CH',
        'competition': 'CO',
    }
    return abbrevs.get(key, key[:2].upper())


def format_date(dt) -> str:
    """
    Format datetime for display.

    Args:
        dt: datetime object

    Returns:
        Formatted date string (e.g., "Jan 15, 2026")
    """
    return dt.strftime("%b %d, %Y")


def format_datetime(dt) -> str:
    """
    Format datetime with time for display.

    Args:
        dt: datetime object

    Returns:
        Formatted datetime string (e.g., "Jan 15, 2026 10:30 AM")
    """
    return dt.strftime("%b %d, %Y %I:%M %p")


def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Truncate text to max length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length before truncation
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def get_gong_call_link(call_id: str) -> str:
    """
    Generate Gong web UI link for a call.

    Args:
        call_id: Gong call ID

    Returns:
        Full URL to view call in Gong web UI
    """
    # Gong web UI is always at app.gong.io regardless of API region
    return f"https://app.gong.io/call?id={call_id}"


def format_gong_link_markdown(call_id: str, label: str = "View in Gong") -> str:
    """
    Format a Gong call link as Markdown.

    Args:
        call_id: Gong call ID
        label: Link text

    Returns:
        Markdown formatted link
    """
    url = get_gong_call_link(call_id)
    return f"[🔗 {label}]({url})"
