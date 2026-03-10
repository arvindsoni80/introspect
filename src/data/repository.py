"""Repository for data access operations."""

import sqlite3
from datetime import datetime, date
from typing import Optional, List, Dict

from ..domain import (
    SalesRep, Account, AccountRepHistory, StageTransition,
    Call, StageClassificationResult,
    MEDDPICCScores, CallMEDDPICCScores,
    TrialScores, CallTrialScores,
    CloseScores, CallCloseScores,
    WinLossAnalysis, CallWinLossAnalysis,
)
from ..services.persona_classifier import PersonaClassifier


class Repository:
    """Data access layer for all domain entities."""

    def __init__(self, conn: sqlite3.Connection):
        """
        Initialize repository with database connection.

        Args:
            conn: Active SQLite connection with row_factory set
        """
        self.conn = conn

    # ========================================================================
    # Sales Rep Operations
    # ========================================================================

    def create_sales_rep(self, rep: SalesRep) -> SalesRep:
        """Create a new sales rep."""
        cursor = self.conn.execute("""
            INSERT INTO sales_reps (email, segment, joining_date, is_active, left_date)
            VALUES (?, ?, ?, ?, ?)
        """, (rep.email, rep.segment, rep.joining_date.isoformat(),
              rep.is_active, rep.left_date.isoformat() if rep.left_date else None))

        self.conn.commit()
        return self.get_sales_rep(rep.email)

    def get_sales_rep(self, email: str) -> Optional[SalesRep]:
        """Get sales rep by email."""
        cursor = self.conn.execute("""
            SELECT * FROM sales_reps WHERE email = ?
        """, (email,))

        row = cursor.fetchone()
        if not row:
            return None

        return SalesRep(
            email=row['email'],
            segment=row['segment'],
            joining_date=date.fromisoformat(row['joining_date']),
            is_active=bool(row['is_active']),
            left_date=date.fromisoformat(row['left_date']) if row['left_date'] else None,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )

    def list_sales_reps(self, active_only: bool = False) -> List[SalesRep]:
        """List all sales reps, optionally filtering for active only."""
        query = "SELECT * FROM sales_reps"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY email"

        cursor = self.conn.execute(query)
        reps = []
        for row in cursor.fetchall():
            reps.append(SalesRep(
                email=row['email'],
                segment=row['segment'],
                joining_date=date.fromisoformat(row['joining_date']),
                is_active=bool(row['is_active']),
                left_date=date.fromisoformat(row['left_date']) if row['left_date'] else None,
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
            ))
        return reps

    def update_sales_rep(self, rep: SalesRep) -> SalesRep:
        """Update sales rep."""
        self.conn.execute("""
            UPDATE sales_reps
            SET segment = ?, is_active = ?, left_date = ?, updated_at = datetime('now')
            WHERE email = ?
        """, (rep.segment, rep.is_active,
              rep.left_date.isoformat() if rep.left_date else None, rep.email))

        self.conn.commit()
        return self.get_sales_rep(rep.email)

    # ========================================================================
    # Account Operations
    # ========================================================================

    def create_account(self, account: Account) -> Account:
        """Create a new account."""
        cursor = self.conn.execute("""
            INSERT INTO accounts (
                domain, current_stage, deal_status,
                primary_sales_rep, primary_segment, first_call_date, last_call_date,
                total_calls
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            account.domain, account.current_stage, account.deal_status,
            account.primary_sales_rep, account.primary_segment,
            account.first_call_date.isoformat() if account.first_call_date else None,
            account.last_call_date.isoformat() if account.last_call_date else None,
            account.total_calls
        ))

        self.conn.commit()
        return self.get_account_by_id(cursor.lastrowid)

    def get_account_by_id(self, account_id: int) -> Optional[Account]:
        """Get account by ID."""
        cursor = self.conn.execute("""
            SELECT * FROM accounts WHERE id = ?
        """, (account_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return self._row_to_account(row)

    def get_account(self, account_id: int) -> Optional[Account]:
        """Get account by ID (alias for get_account_by_id)."""
        return self.get_account_by_id(account_id)

    def get_account_by_domain(self, domain: str) -> Optional[Account]:
        """Get account by domain."""
        cursor = self.conn.execute("""
            SELECT * FROM accounts WHERE domain = ?
        """, (domain,))

        row = cursor.fetchone()
        if not row:
            return None

        return self._row_to_account(row)

    def list_accounts(self, stage: Optional[str] = None,
                     deal_status: Optional[str] = None) -> List[Account]:
        """List accounts with optional filters."""
        query = "SELECT * FROM accounts WHERE 1=1"
        params = []

        if stage:
            query += " AND current_stage = ?"
            params.append(stage)

        if deal_status:
            query += " AND deal_status = ?"
            params.append(deal_status)

        query += " ORDER BY last_call_date DESC"

        cursor = self.conn.execute(query, params)
        return [self._row_to_account(row) for row in cursor.fetchall()]

    def update_account(self, account: Account) -> Account:
        """Update account."""
        self.conn.execute("""
            UPDATE accounts
            SET current_stage = ?, deal_status = ?,
                primary_sales_rep = ?, primary_segment = ?,
                first_call_date = ?, last_call_date = ?,
                total_calls = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (
            account.current_stage, account.deal_status,
            account.primary_sales_rep, account.primary_segment,
            account.first_call_date.isoformat() if account.first_call_date else None,
            account.last_call_date.isoformat() if account.last_call_date else None,
            account.total_calls,
            account.id
        ))

        self.conn.commit()
        return self.get_account_by_id(account.id)

    def _row_to_account(self, row) -> Account:
        """Convert database row to Account object."""
        return Account(
            id=row['id'],
            domain=row['domain'],
            current_stage=row['current_stage'],
            deal_status=row['deal_status'],
            primary_sales_rep=row['primary_sales_rep'],
            primary_segment=row['primary_segment'],
            first_call_date=datetime.fromisoformat(row['first_call_date']) if row['first_call_date'] else None,
            last_call_date=datetime.fromisoformat(row['last_call_date']) if row['last_call_date'] else None,
            total_calls=row['total_calls'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )

    # ========================================================================
    # Call Operations
    # ========================================================================

    def create_call(self, call: Call) -> Call:
        """Create a new call."""
        self.conn.execute("""
            INSERT INTO calls (
                call_id, account_id, sales_rep_email, call_date, call_title,
                primary_stage, secondary_stage, stage_confidence, segment_at_call_time
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            call.call_id, call.account_id, call.sales_rep_email,
            call.call_date.isoformat(), call.call_title,
            call.primary_stage, call.secondary_stage, call.stage_confidence,
            call.segment_at_call_time
        ))

        self.conn.commit()
        return self.get_call_by_gong_id(call.call_id)

    def get_call_by_gong_id(self, gong_call_id: str) -> Optional[Call]:
        """Get call by Gong call ID."""
        cursor = self.conn.execute("""
            SELECT * FROM calls WHERE call_id = ?
        """, (gong_call_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return self._row_to_call(row)

    def list_calls_by_account(self, account_id: int) -> List[Call]:
        """List all calls for an account."""
        cursor = self.conn.execute("""
            SELECT * FROM calls WHERE account_id = ?
            ORDER BY call_date DESC
        """, (account_id,))

        return [self._row_to_call(row) for row in cursor.fetchall()]

    def list_calls_by_stage(self, stage: str) -> List[Call]:
        """List all calls for a specific stage."""
        cursor = self.conn.execute("""
            SELECT * FROM calls WHERE primary_stage = ?
            ORDER BY call_date DESC
        """, (stage,))

        return [self._row_to_call(row) for row in cursor.fetchall()]

    def _row_to_call(self, row) -> Call:
        """Convert database row to Call object."""
        return Call(
            call_id=row['call_id'],
            account_id=row['account_id'],
            sales_rep_email=row['sales_rep_email'],
            call_date=datetime.fromisoformat(row['call_date']),
            call_title=row['call_title'],
            primary_stage=row['primary_stage'],
            secondary_stage=row['secondary_stage'],
            stage_confidence=row['stage_confidence'],
            segment_at_call_time=row['segment_at_call_time'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )

    # ========================================================================
    # MEDDPICC Score Operations
    # ========================================================================

    def create_call_meddpicc_scores(self, scores: CallMEDDPICCScores) -> CallMEDDPICCScores:
        """Create MEDDPICC scores for a call."""
        cursor = self.conn.execute("""
            INSERT INTO call_meddpicc_scores (
                call_id, metrics, economic_buyer, decision_criteria, decision_process,
                paper_process, identify_pain, champion, competition, overall_score,
                meddpicc_summary, key_gaps, clarity_of_need, key_influencers,
                next_steps, trial_readiness
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scores.call_id,
            scores.scores.metrics, scores.scores.economic_buyer,
            scores.scores.decision_criteria, scores.scores.decision_process,
            scores.scores.paper_process, scores.scores.identify_pain,
            scores.scores.champion, scores.scores.competition,
            scores.scores.overall_score,
            scores.scores.meddpicc_summary, scores.scores.key_gaps,
            scores.scores.clarity_of_need, scores.scores.key_influencers,
            scores.scores.next_steps, scores.scores.trial_readiness
        ))

        self.conn.commit()
        return self.get_call_meddpicc_scores(scores.call_id)

    def get_call_meddpicc_scores(self, call_id: str) -> Optional[CallMEDDPICCScores]:
        """Get MEDDPICC scores for a call."""
        cursor = self.conn.execute("""
            SELECT * FROM call_meddpicc_scores WHERE call_id = ?
        """, (call_id,))

        row = cursor.fetchone()
        if not row:
            return None

        scores = MEDDPICCScores(
            metrics=row['metrics'],
            economic_buyer=row['economic_buyer'],
            decision_criteria=row['decision_criteria'],
            decision_process=row['decision_process'],
            paper_process=row['paper_process'],
            identify_pain=row['identify_pain'],
            champion=row['champion'],
            competition=row['competition'],
            overall_score=row['overall_score'],
            meddpicc_summary=row['meddpicc_summary'],
            key_gaps=row['key_gaps'],
            clarity_of_need=row['clarity_of_need'],
            key_influencers=row['key_influencers'],
            next_steps=row['next_steps'],
            trial_readiness=row['trial_readiness'],
        )

        return CallMEDDPICCScores(
            call_id=row['call_id'],
            scores=scores,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )

    # ========================================================================
    # Trial Score Operations
    # ========================================================================

    def create_call_trial_scores(self, scores: CallTrialScores) -> CallTrialScores:
        """Create trial scores for a call."""
        cursor = self.conn.execute("""
            INSERT INTO call_trial_scores (
                call_id, technical_validation, readiness_progress, internal_adoption,
                advocacy_sentiment, landscape_competition, overall_score,
                health_interpretation, primary_concern_category, concern_severity,
                likelihood_to_advance, is_bake_off, key_concerns,
                recommended_actions, next_steps
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scores.call_id,
            scores.scores.technical_validation, scores.scores.readiness_progress,
            scores.scores.internal_adoption, scores.scores.advocacy_sentiment,
            scores.scores.landscape_competition, scores.scores.overall_score,
            scores.scores.health_interpretation, scores.scores.primary_concern_category,
            scores.scores.concern_severity, scores.scores.likelihood_to_advance,
            scores.scores.is_bake_off, scores.scores.key_concerns,
            scores.scores.recommended_actions, scores.scores.next_steps
        ))

        self.conn.commit()
        return self.get_call_trial_scores(scores.call_id)

    def get_call_trial_scores(self, call_id: str) -> Optional[CallTrialScores]:
        """Get trial scores for a call."""
        cursor = self.conn.execute("""
            SELECT * FROM call_trial_scores WHERE call_id = ?
        """, (call_id,))

        row = cursor.fetchone()
        if not row:
            return None

        scores = TrialScores(
            technical_validation=row['technical_validation'],
            readiness_progress=row['readiness_progress'],
            internal_adoption=row['internal_adoption'],
            advocacy_sentiment=row['advocacy_sentiment'],
            landscape_competition=row['landscape_competition'],
            overall_score=row['overall_score'],
            health_interpretation=row['health_interpretation'],
            primary_concern_category=row['primary_concern_category'],
            concern_severity=row['concern_severity'],
            likelihood_to_advance=row['likelihood_to_advance'],
            is_bake_off=bool(row['is_bake_off']),
            key_concerns=row['key_concerns'],
            recommended_actions=row['recommended_actions'],
            next_steps=row['next_steps'],
        )

        return CallTrialScores(
            call_id=row['call_id'],
            scores=scores,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )

    # ========================================================================
    # Close Score Operations
    # ========================================================================

    def create_call_close_scores(self, scores: CallCloseScores) -> CallCloseScores:
        """Create close scores for a call."""
        cursor = self.conn.execute("""
            INSERT INTO call_close_scores (
                call_id, commercial_alignment, legal_compliance, organizational_consensus,
                single_threading_risk, execution_momentum, overall_score,
                health_interpretation, primary_concern_category, concern_severity,
                likelihood_to_close, has_competitive_pressure, key_concerns,
                recommended_actions, next_steps
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scores.call_id,
            scores.scores.commercial_alignment, scores.scores.legal_compliance,
            scores.scores.organizational_consensus, scores.scores.single_threading_risk,
            scores.scores.execution_momentum, scores.scores.overall_score,
            scores.scores.health_interpretation, scores.scores.primary_concern_category,
            scores.scores.concern_severity, scores.scores.likelihood_to_close,
            scores.scores.has_competitive_pressure, scores.scores.key_concerns,
            scores.scores.recommended_actions, scores.scores.next_steps
        ))

        self.conn.commit()
        return self.get_call_close_scores(scores.call_id)

    def get_call_close_scores(self, call_id: str) -> Optional[CallCloseScores]:
        """Get close scores for a call."""
        cursor = self.conn.execute("""
            SELECT * FROM call_close_scores WHERE call_id = ?
        """, (call_id,))

        row = cursor.fetchone()
        if not row:
            return None

        scores = CloseScores(
            commercial_alignment=row['commercial_alignment'],
            legal_compliance=row['legal_compliance'],
            organizational_consensus=row['organizational_consensus'],
            single_threading_risk=row['single_threading_risk'],
            execution_momentum=row['execution_momentum'],
            overall_score=row['overall_score'],
            health_interpretation=row['health_interpretation'],
            primary_concern_category=row['primary_concern_category'],
            concern_severity=row['concern_severity'],
            likelihood_to_close=row['likelihood_to_close'],
            has_competitive_pressure=bool(row['has_competitive_pressure']),
            key_concerns=row['key_concerns'],
            recommended_actions=row['recommended_actions'],
            next_steps=row['next_steps'],
        )

        return CallCloseScores(
            call_id=row['call_id'],
            scores=scores,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )

    # ========================================================================
    # Win/Loss Analysis Operations
    # ========================================================================

    def create_call_win_loss_analysis(self, analysis: CallWinLossAnalysis) -> CallWinLossAnalysis:
        """Create win/loss analysis for a call."""
        cursor = self.conn.execute("""
            INSERT INTO call_win_loss_analysis (
                call_id, outcome, primary_reasons, stage_of_decision,
                critical_dimensions, competitive_factor, key_learnings, verbatim_quotes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            analysis.call_id,
            analysis.analysis.outcome, analysis.analysis.primary_reasons,
            analysis.analysis.stage_of_decision, analysis.analysis.critical_dimensions,
            analysis.analysis.competitive_factor, analysis.analysis.key_learnings,
            analysis.analysis.verbatim_quotes
        ))

        self.conn.commit()
        return self.get_call_win_loss_analysis(analysis.call_id)

    def get_call_win_loss_analysis(self, call_id: str) -> Optional[CallWinLossAnalysis]:
        """Get win/loss analysis for a call."""
        cursor = self.conn.execute("""
            SELECT * FROM call_win_loss_analysis WHERE call_id = ?
        """, (call_id,))

        row = cursor.fetchone()
        if not row:
            return None

        analysis = WinLossAnalysis(
            outcome=row['outcome'],
            primary_reasons=row['primary_reasons'],
            stage_of_decision=row['stage_of_decision'],
            critical_dimensions=row['critical_dimensions'],
            competitive_factor=row['competitive_factor'],
            key_learnings=row['key_learnings'],
            verbatim_quotes=row['verbatim_quotes'],
        )

        return CallWinLossAnalysis(
            call_id=row['call_id'],
            analysis=analysis,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )

    # ========================================================================
    # Stage Transition Operations
    # ========================================================================

    def create_stage_transition(self, transition: StageTransition) -> StageTransition:
        """Record a stage transition."""
        cursor = self.conn.execute("""
            INSERT INTO stage_transitions (
                account_id, from_stage, to_stage, transitioned_at,
                duration_in_previous_stage_days, triggered_by_call_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            transition.account_id, transition.from_stage, transition.to_stage,
            transition.transitioned_at.isoformat(),
            transition.duration_in_previous_stage_days,
            transition.triggered_by_call_id
        ))

        self.conn.commit()

        return StageTransition(
            id=cursor.lastrowid,
            account_id=transition.account_id,
            from_stage=transition.from_stage,
            to_stage=transition.to_stage,
            transitioned_at=transition.transitioned_at,
            duration_in_previous_stage_days=transition.duration_in_previous_stage_days,
            triggered_by_call_id=transition.triggered_by_call_id,
        )

    def list_stage_transitions(self, account_id: int) -> List[StageTransition]:
        """Get all stage transitions for an account."""
        cursor = self.conn.execute("""
            SELECT * FROM stage_transitions WHERE account_id = ?
            ORDER BY transitioned_at ASC
        """, (account_id,))

        transitions = []
        for row in cursor.fetchall():
            transitions.append(StageTransition(
                id=row['id'],
                account_id=row['account_id'],
                from_stage=row['from_stage'],
                to_stage=row['to_stage'],
                transitioned_at=datetime.fromisoformat(row['transitioned_at']),
                duration_in_previous_stage_days=row['duration_in_previous_stage_days'],
                triggered_by_call_id=row['triggered_by_call_id'],
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            ))
        return transitions

    # ========================================================================
    # Account Rep History Operations
    # ========================================================================

    def upsert_account_rep_history(self, history: AccountRepHistory) -> AccountRepHistory:
        """Insert or update account rep history."""
        self.conn.execute("""
            INSERT INTO account_rep_history (
                account_id, sales_rep_email, first_call_date, last_call_date, total_calls
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(account_id, sales_rep_email) DO UPDATE SET
                last_call_date = excluded.last_call_date,
                total_calls = excluded.total_calls,
                updated_at = datetime('now')
        """, (
            history.account_id, history.sales_rep_email,
            history.first_call_date.isoformat(),
            history.last_call_date.isoformat() if history.last_call_date else None,
            history.total_calls
        ))

        self.conn.commit()

        cursor = self.conn.execute("""
            SELECT * FROM account_rep_history
            WHERE account_id = ? AND sales_rep_email = ?
        """, (history.account_id, history.sales_rep_email))

        row = cursor.fetchone()
        return AccountRepHistory(
            id=row['id'],
            account_id=row['account_id'],
            sales_rep_email=row['sales_rep_email'],
            first_call_date=datetime.fromisoformat(row['first_call_date']),
            last_call_date=datetime.fromisoformat(row['last_call_date']) if row['last_call_date'] else None,
            total_calls=row['total_calls'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )

    # =========================================================================
    # Call Participants
    # =========================================================================

    def store_call_participants(self, call_id: str, participants: List[Dict]) -> int:
        """
        Store participants for a call.

        Args:
            call_id: Call ID
            participants: List of participant dicts from Gong API parties data

        Returns:
            Number of participants inserted (only those with speaker_id)
        """
        # Delete existing participants for this call (in case of re-processing)
        self.conn.execute("DELETE FROM call_participants WHERE call_id = ?", (call_id,))

        # Insert participants (only those with speaker_id)
        inserted_count = 0
        for participant in participants:
            speaker_id = participant.get('speakerId')

            # Skip if no speaker_id (we need this to match against transcripts)
            if not speaker_id:
                continue

            # Classify persona based on title (only for external participants)
            title = participant.get('title', '')
            affiliation = participant.get('affiliation', '')
            persona = None
            if affiliation == 'External':
                persona = PersonaClassifier.classify(title)

            self.conn.execute("""
                INSERT INTO call_participants (
                    call_id, speaker_id, party_id, user_id,
                    email_address, name, title, affiliation, phone_number, persona
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                call_id,
                speaker_id,
                participant.get('id'),
                participant.get('userId'),
                participant.get('emailAddress'),
                participant.get('name'),
                title,
                affiliation,
                participant.get('phoneNumber'),
                persona,
            ))
            inserted_count += 1

        self.conn.commit()
        return inserted_count

    def get_call_participants(self, call_id: str) -> Dict[str, Dict]:
        """
        Get participants for a call, indexed by speaker_id.

        Args:
            call_id: Call ID

        Returns:
            Dictionary mapping speaker_id -> participant info
        """
        cursor = self.conn.execute("""
            SELECT * FROM call_participants
            WHERE call_id = ?
        """, (call_id,))

        participants = {}
        for row in cursor.fetchall():
            speaker_id = row['speaker_id']

            # Handle new columns safely (may not exist in older databases)
            try:
                speaker_questions = row['speaker_questions']
                question_count = row['question_count'] if row['question_count'] is not None else 0
            except (KeyError, IndexError):
                speaker_questions = None
                question_count = 0

            try:
                persona = row['persona']
            except (KeyError, IndexError):
                persona = None

            participants[speaker_id] = {
                'speaker_id': speaker_id,
                'party_id': row['party_id'],
                'user_id': row['user_id'],
                'email_address': row['email_address'],
                'name': row['name'],
                'title': row['title'],
                'affiliation': row['affiliation'],
                'phone_number': row['phone_number'],
                'speaker_questions': speaker_questions,
                'question_count': question_count,
                'persona': persona,
            }

        return participants

    def enrich_transcript_with_participants(self, call_id: str, transcript: str) -> str:
        """
        Enrich a transcript by replacing speaker IDs with participant names and roles.

        Args:
            call_id: Call ID
            transcript: Raw transcript with speaker IDs like "[123456]: text"

        Returns:
            Enriched transcript with format like "[Sales - John]: text"
        """
        # Get participants for this call
        participants = self.get_call_participants(call_id)

        if not participants:
            # No participant data available, return as-is
            return transcript

        # Replace speaker IDs in transcript
        enriched_lines = []
        for line in transcript.split('\n'):
            if not line.strip():
                enriched_lines.append(line)
                continue

            # Parse line format: "[speakerId]: text"
            if line.startswith('[') and ']:' in line:
                end_bracket = line.find(']:')
                speaker_id = line[1:end_bracket]
                text = line[end_bracket + 2:]  # Skip "]: "

                # Look up participant info
                participant = participants.get(speaker_id)

                if participant:
                    # Format: [Role - Name]: text
                    affiliation = participant.get('affiliation', 'Unknown')
                    name = participant.get('name', 'Unknown')

                    # Map affiliation to role
                    if affiliation == 'Internal':
                        role = 'Sales'
                    elif affiliation == 'External':
                        role = 'Customer'
                    else:
                        role = 'Unknown'

                    enriched_line = f"[{role} - {name}]: {text}"
                else:
                    # No participant info for this speaker, keep original
                    enriched_line = line

                enriched_lines.append(enriched_line)
            else:
                # Line doesn't match expected format, keep as-is
                enriched_lines.append(line)

        return '\n'.join(enriched_lines)
