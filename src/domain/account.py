"""Account domain model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Account:
    """Account (identified by email domain)."""

    id: Optional[int]
    domain: str
    current_stage: Optional[str] = None
    deal_status: Optional[str] = None
    primary_sales_rep: Optional[str] = None
    primary_segment: Optional[str] = None
    first_call_date: Optional[datetime] = None
    last_call_date: Optional[datetime] = None
    total_calls: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def is_active(self) -> bool:
        """Check if account is in active status."""
        return self.deal_status == 'active'

    def is_closed(self) -> bool:
        """Check if account is closed (won or lost)."""
        return self.deal_status in ('closed_won', 'closed_lost')

    def is_stalled(self) -> bool:
        """Check if account is stalled."""
        return self.deal_status == 'stalled'

    def days_in_current_stage(self) -> Optional[int]:
        """Calculate days in current stage (today - last_call_date)."""
        if self.last_call_date is None:
            return None

        # Strip timezone info to make comparison work
        last_call = self.last_call_date.replace(tzinfo=None) if self.last_call_date.tzinfo else self.last_call_date
        now = datetime.now()

        delta = now - last_call
        return delta.days


@dataclass
class AccountRepHistory:
    """Track which reps worked on which accounts."""

    id: Optional[int]
    account_id: int
    sales_rep_email: str
    first_call_date: datetime
    last_call_date: Optional[datetime] = None
    total_calls: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class StageTransition:
    """Track account stage transitions."""

    id: Optional[int]
    account_id: int
    from_stage: str
    to_stage: str
    transitioned_at: datetime
    duration_in_previous_stage_days: Optional[int] = None
    triggered_by_call_id: Optional[int] = None
    created_at: Optional[datetime] = None
