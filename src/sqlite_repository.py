"""SQLite implementation of CallRepository."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import AccountCall, AccountRecord, CallAnalysis, MEDDPICCScores
from .repository import CallRepository


class SQLiteCallRepository(CallRepository):
    """SQLite-based storage for account call history."""

    def __init__(self, db_path: str):
        """
        Initialize SQLite repository.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        # Account-level MEDDPICC data (discovery calls only)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                domain TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                calls TEXT NOT NULL,
                overall_meddpicc TEXT NOT NULL
            )
        """)

        # Track all evaluated calls (deduplication + reasoning)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS evaluated_calls (
                call_id TEXT PRIMARY KEY,
                evaluated_at TEXT NOT NULL,
                is_discovery INTEGER NOT NULL,
                reason TEXT
            )
        """)

        # Sales rep attributes
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sales_reps (
                email TEXT PRIMARY KEY,
                segment TEXT NOT NULL,
                joining_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        self.conn.commit()

    async def get_account(self, domain: str) -> Optional[AccountRecord]:
        """Get account record by domain."""
        cursor = self.conn.execute(
            "SELECT domain, created_at, updated_at, calls, overall_meddpicc FROM accounts WHERE domain = ?",
            (domain,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        domain, created_at, updated_at, calls_json, overall_json = row

        return AccountRecord(
            domain=domain,
            created_at=datetime.fromisoformat(created_at),
            updated_at=datetime.fromisoformat(updated_at),
            calls=[AccountCall(**c) for c in json.loads(calls_json)],
            overall_meddpicc=MEDDPICCScores(**json.loads(overall_json)),
        )

    async def upsert_account(self, account: AccountRecord) -> None:
        """Insert or update account record."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO accounts (domain, created_at, updated_at, calls, overall_meddpicc)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                account.domain,
                account.created_at.isoformat(),
                account.updated_at.isoformat(),
                json.dumps([c.model_dump(mode="json") for c in account.calls], default=str),
                json.dumps(account.overall_meddpicc.model_dump(), default=str),
            ),
        )
        self.conn.commit()

    async def add_discovery_call(
        self, domain: str, call_analysis: CallAnalysis
    ) -> AccountRecord:
        """Add a discovery call and update overall MEDDPICC."""
        # Get existing account or create new
        account = await self.get_account(domain)

        # Extract external participants
        external_participants = call_analysis.participants.external

        # Create call record with reasoning and notes
        new_call = AccountCall(
            call_id=call_analysis.call_id,
            call_date=call_analysis.call_date,
            sales_rep=call_analysis.sales_rep_email,
            external_participants=external_participants,
            meddpicc_scores=call_analysis.meddpicc_scores,
            meddpicc_summary=call_analysis.meddpicc_summary,
            analysis_notes=call_analysis.analysis_notes,
        )

        if account is None:
            # Create new account
            account = AccountRecord(
                domain=domain,
                created_at=call_analysis.call_date,
                updated_at=call_analysis.call_date,
                calls=[new_call],
                overall_meddpicc=call_analysis.meddpicc_scores,
            )
        else:
            # Update existing account
            account.calls.append(new_call)
            account.updated_at = call_analysis.call_date

            # Recalculate overall MEDDPICC (max of each dimension)
            account.overall_meddpicc = self._calculate_overall_meddpicc(account.calls)

        # Save to database
        await self.upsert_account(account)

        return account

    def _calculate_overall_meddpicc(self, calls: list[AccountCall]) -> MEDDPICCScores:
        """Calculate overall MEDDPICC as max of each dimension across all calls."""
        all_scores = [call.meddpicc_scores for call in calls]

        return MEDDPICCScores(
            metrics=max(s.metrics for s in all_scores),
            economic_buyer=max(s.economic_buyer for s in all_scores),
            decision_criteria=max(s.decision_criteria for s in all_scores),
            decision_process=max(s.decision_process for s in all_scores),
            paper_process=max(s.paper_process for s in all_scores),
            identify_pain=max(s.identify_pain for s in all_scores),
            champion=max(s.champion for s in all_scores),
            competition=max(s.competition for s in all_scores),
            overall_score=max(s.overall_score for s in all_scores),
        )

    async def list_domains(self) -> list[str]:
        """List all tracked domains."""
        cursor = self.conn.execute("SELECT domain FROM accounts ORDER BY domain")
        return [row[0] for row in cursor.fetchall()]

    async def get_all_accounts(self) -> list[AccountRecord]:
        """Get all account records."""
        cursor = self.conn.execute(
            "SELECT domain, created_at, updated_at, calls, overall_meddpicc FROM accounts ORDER BY domain"
        )
        accounts = []
        for row in cursor.fetchall():
            domain, created_at, updated_at, calls_json, overall_json = row
            accounts.append(
                AccountRecord(
                    domain=domain,
                    created_at=datetime.fromisoformat(created_at),
                    updated_at=datetime.fromisoformat(updated_at),
                    calls=[AccountCall(**c) for c in json.loads(calls_json)],
                    overall_meddpicc=MEDDPICCScores(**json.loads(overall_json)),
                )
            )
        return accounts

    async def call_exists(self, call_id: str) -> bool:
        """Check if a call has already been evaluated."""
        cursor = self.conn.execute(
            "SELECT 1 FROM evaluated_calls WHERE call_id = ?",
            (call_id,)
        )
        return cursor.fetchone() is not None

    async def store_evaluated_call(
        self, call_id: str, is_discovery: bool, reason: Optional[str] = None
    ) -> None:
        """
        Store that a call has been evaluated.

        Args:
            call_id: Unique call identifier
            is_discovery: Whether call was classified as discovery
            reason: Why it's NOT a discovery call (only if is_discovery=False)
        """
        self.conn.execute(
            """
            INSERT OR REPLACE INTO evaluated_calls (call_id, evaluated_at, is_discovery, reason)
            VALUES (?, ?, ?, ?)
            """,
            (
                call_id,
                datetime.now().isoformat(),
                1 if is_discovery else 0,
                reason if not is_discovery else None,
            ),
        )
        self.conn.commit()

    async def close(self) -> None:
        """Close database connection."""
        self.conn.close()
