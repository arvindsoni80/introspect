"""Score domain models for all evaluation frameworks."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


# ============================================================================
# Discovery Stage - MEDDPICC Scores
# ============================================================================

@dataclass
class MEDDPICCScores:
    """MEDDPICC discovery scores (0/2/5 scale)."""

    # Dimensions (0/2/5)
    metrics: int
    economic_buyer: int
    decision_criteria: int
    decision_process: int
    paper_process: int
    identify_pain: int
    champion: int
    competition: int

    # Aggregated
    overall_score: float

    # Analysis
    meddpicc_summary: Optional[str] = None
    key_gaps: Optional[str] = None
    clarity_of_need: Optional[str] = None
    key_influencers: Optional[str] = None
    next_steps: Optional[str] = None
    trial_readiness: Optional[str] = None

    def __post_init__(self):
        """Validate scores and calculate overall if not provided."""
        # Validate dimension scores
        for field in ['metrics', 'economic_buyer', 'decision_criteria', 'decision_process',
                      'paper_process', 'identify_pain', 'champion', 'competition']:
            value = getattr(self, field)
            if value not in (0, 2, 5):
                raise ValueError(f"{field} must be 0, 2, or 5, got {value}")

        # Calculate overall score if needed
        if self.overall_score is None:
            self.overall_score = self.calculate_overall()

    def calculate_overall(self) -> float:
        """Calculate average of all dimensions."""
        scores = [
            self.metrics, self.economic_buyer, self.decision_criteria,
            self.decision_process, self.paper_process, self.identify_pain,
            self.champion, self.competition
        ]
        return round(sum(scores) / len(scores), 1)

    def get_weakest_dimensions(self, threshold: int = 2) -> List[tuple]:
        """Get dimensions scoring below threshold."""
        dimensions = [
            ('metrics', self.metrics),
            ('economic_buyer', self.economic_buyer),
            ('decision_criteria', self.decision_criteria),
            ('decision_process', self.decision_process),
            ('paper_process', self.paper_process),
            ('identify_pain', self.identify_pain),
            ('champion', self.champion),
            ('competition', self.competition),
        ]
        return [(name, score) for name, score in dimensions if score <= threshold]


@dataclass
class CallMEDDPICCScores:
    """Call-level MEDDPICC scores with metadata."""

    call_id: str  # Gong call ID (PRIMARY KEY)
    scores: MEDDPICCScores
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================================
# Trial Stage - TRIAL Health Scores
# ============================================================================

@dataclass
class TrialScores:
    """TRIAL health scores (0/2/5 scale, higher = healthier)."""

    # Dimensions (0/2/5)
    technical_validation: int
    readiness_progress: int
    internal_adoption: int
    advocacy_sentiment: int
    landscape_competition: int

    # Aggregated
    overall_score: float

    # Analysis
    health_interpretation: Optional[str] = None  # 'healthy', 'at_risk', 'critical'
    primary_concern_category: Optional[str] = None  # 'technical', 'adoption', etc.
    concern_severity: Optional[str] = None  # 'critical', 'high', 'medium', 'low', 'none'
    likelihood_to_advance: Optional[str] = None  # 'high', 'medium', 'low'
    is_bake_off: bool = False
    key_concerns: Optional[str] = None
    recommended_actions: Optional[str] = None
    next_steps: Optional[str] = None

    def __post_init__(self):
        """Validate scores and calculate overall if not provided."""
        # Validate dimension scores
        for field in ['technical_validation', 'readiness_progress', 'internal_adoption',
                      'advocacy_sentiment', 'landscape_competition']:
            value = getattr(self, field)
            if value not in (0, 2, 5):
                raise ValueError(f"{field} must be 0, 2, or 5, got {value}")

        # Calculate overall score if needed
        if self.overall_score is None:
            self.overall_score = self.calculate_overall()

        # Determine health interpretation if not provided
        if self.health_interpretation is None:
            self.health_interpretation = self.determine_health()

    def calculate_overall(self) -> float:
        """Calculate average of all dimensions."""
        scores = [
            self.technical_validation, self.readiness_progress,
            self.internal_adoption, self.advocacy_sentiment,
            self.landscape_competition
        ]
        return round(sum(scores) / len(scores), 1)

    def determine_health(self) -> str:
        """Determine health interpretation based on score."""
        if self.overall_score >= 4.0:
            return 'healthy'
        elif self.overall_score >= 2.5:
            return 'at_risk'
        else:
            return 'critical'


@dataclass
class CallTrialScores:
    """Call-level trial scores with metadata."""

    call_id: str  # Gong call ID (PRIMARY KEY)
    scores: TrialScores
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================================
# Negotiation Stage - CLOSE Health Scores
# ============================================================================

@dataclass
class CloseScores:
    """CLOSE health scores (0/2/5 scale, higher = healthier)."""

    # Dimensions (0/2/5)
    commercial_alignment: int
    legal_compliance: int
    organizational_consensus: int
    single_threading_risk: int
    execution_momentum: int

    # Aggregated
    overall_score: float

    # Analysis
    health_interpretation: Optional[str] = None  # 'healthy', 'at_risk', 'critical'
    primary_concern_category: Optional[str] = None  # 'commercial', 'technical', etc.
    concern_severity: Optional[str] = None  # 'critical', 'high', 'medium', 'low', 'none'
    likelihood_to_close: Optional[str] = None  # 'high', 'medium', 'low'
    has_competitive_pressure: bool = False
    key_concerns: Optional[str] = None
    recommended_actions: Optional[str] = None
    next_steps: Optional[str] = None

    def __post_init__(self):
        """Validate scores and calculate overall if not provided."""
        # Validate dimension scores
        for field in ['commercial_alignment', 'legal_compliance', 'organizational_consensus',
                      'single_threading_risk', 'execution_momentum']:
            value = getattr(self, field)
            if value not in (0, 2, 5):
                raise ValueError(f"{field} must be 0, 2, or 5, got {value}")

        # Calculate overall score if needed
        if self.overall_score is None:
            self.overall_score = self.calculate_overall()

        # Determine health interpretation if not provided
        if self.health_interpretation is None:
            self.health_interpretation = self.determine_health()

    def calculate_overall(self) -> float:
        """Calculate average of all dimensions."""
        scores = [
            self.commercial_alignment, self.legal_compliance,
            self.organizational_consensus, self.single_threading_risk,
            self.execution_momentum
        ]
        return round(sum(scores) / len(scores), 1)

    def determine_health(self) -> str:
        """Determine health interpretation based on score."""
        if self.overall_score >= 4.0:
            return 'healthy'
        elif self.overall_score >= 2.5:
            return 'at_risk'
        else:
            return 'critical'


@dataclass
class CallCloseScores:
    """Call-level close scores with metadata."""

    call_id: str  # Gong call ID (PRIMARY KEY)
    scores: CloseScores
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================================
# Closed Stage - Win/Loss Analysis
# ============================================================================

@dataclass
class WinLossAnalysis:
    """Win/loss analysis for closed deals."""

    outcome: str  # 'won' or 'lost'
    primary_reasons: str  # JSON array or pipe-separated
    stage_of_decision: Optional[str] = None  # 'discovery', 'trial', 'negotiation'
    critical_dimensions: Optional[str] = None
    competitive_factor: Optional[str] = None
    key_learnings: Optional[str] = None
    verbatim_quotes: Optional[str] = None

    def __post_init__(self):
        """Validate outcome."""
        if self.outcome not in ('won', 'lost'):
            raise ValueError(f"outcome must be 'won' or 'lost', got {self.outcome}")


@dataclass
class CallWinLossAnalysis:
    """Call-level win/loss analysis with metadata."""

    call_id: str  # Gong call ID (PRIMARY KEY)
    analysis: WinLossAnalysis
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
