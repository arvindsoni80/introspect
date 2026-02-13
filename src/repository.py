"""Repository interface for storing account call history."""

from abc import ABC, abstractmethod
from typing import Optional

from .models import AccountRecord, CallAnalysis


class CallRepository(ABC):
    """Abstract interface for storing and retrieving account call data."""

    @abstractmethod
    async def get_account(self, domain: str) -> Optional[AccountRecord]:
        """
        Get account record by domain.

        Args:
            domain: Email domain (e.g., "sage.com")

        Returns:
            AccountRecord if found, None otherwise
        """
        pass

    @abstractmethod
    async def upsert_account(self, account: AccountRecord) -> None:
        """
        Insert or update account record.

        Args:
            account: AccountRecord to store
        """
        pass

    @abstractmethod
    async def add_discovery_call(
        self, domain: str, call_analysis: CallAnalysis
    ) -> AccountRecord:
        """
        Add a discovery call to an account and update overall MEDDPICC.

        Creates account if it doesn't exist.
        Updates overall_meddpicc to max of all calls.

        Args:
            domain: Email domain
            call_analysis: CallAnalysis with MEDDPICC scores

        Returns:
            Updated AccountRecord
        """
        pass

    @abstractmethod
    async def list_domains(self) -> list[str]:
        """
        List all tracked domains.

        Returns:
            List of domain strings
        """
        pass

    @abstractmethod
    async def call_exists(self, call_id: str) -> bool:
        """
        Check if a call has already been evaluated.

        Args:
            call_id: The call ID to check

        Returns:
            True if call exists in database, False otherwise
        """
        pass

    @abstractmethod
    async def store_evaluated_call(
        self, call_id: str, is_discovery: bool, reason: Optional[str] = None
    ) -> None:
        """
        Store that a call has been evaluated.

        Args:
            call_id: Unique call identifier
            is_discovery: Whether call was classified as discovery
            reason: Why it's NOT a discovery call (only stored if is_discovery=False)
        """
        pass

    @abstractmethod
    async def get_all_accounts(self) -> list[AccountRecord]:
        """
        Get all account records.

        Returns:
            List of all AccountRecord objects
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close any open connections."""
        pass
