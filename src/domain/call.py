"""Call domain model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Call:
    """Sales call."""

    call_id: str  # Gong call ID (PRIMARY KEY)
    account_id: int
    sales_rep_email: str
    call_date: datetime
    primary_stage: str
    call_title: Optional[str] = None
    secondary_stage: Optional[str] = None
    stage_confidence: Optional[float] = None
    segment_at_call_time: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def is_discovery(self) -> bool:
        """Check if this is a discovery call."""
        return self.primary_stage == 'discovery'

    def is_trial(self) -> bool:
        """Check if this is a trial call."""
        return self.primary_stage == 'trial'

    def is_negotiation(self) -> bool:
        """Check if this is a negotiation call."""
        return self.primary_stage == 'negotiation'

    def is_closed(self) -> bool:
        """Check if this is a closed call."""
        return self.primary_stage == 'closed'


@dataclass
class StageClassificationResult:
    """Result of stage classification."""

    primary_stage: str
    confidence: float
    secondary_stage: Optional[str] = None
    reasoning: Optional[str] = None
