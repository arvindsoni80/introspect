"""Sales rep domain model."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class SalesRep:
    """Sales representative."""

    email: str
    segment: str
    joining_date: date
    is_active: bool = True
    left_date: Optional[date] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def days_tenure(self) -> int:
        """Calculate days of tenure."""
        end_date = self.left_date if self.left_date else date.today()
        return (end_date - self.joining_date).days

    @property
    def display_name(self) -> str:
        """Get display name (email without domain)."""
        return self.email.split('@')[0]
