"""Data models for the application."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Participants(BaseModel):
    """Call participants separated by type."""

    internal: list[str] = Field(default_factory=list)
    external: list[str] = Field(default_factory=list)


class MEDDPICCScores(BaseModel):
    """MEDDPICC dimension scores (0-5 scale)."""

    metrics: int = Field(ge=0, le=5)
    economic_buyer: int = Field(ge=0, le=5)
    decision_criteria: int = Field(ge=0, le=5)
    decision_process: int = Field(ge=0, le=5)
    paper_process: int = Field(ge=0, le=5)
    identify_pain: int = Field(ge=0, le=5)
    champion: int = Field(ge=0, le=5)
    competition: int = Field(ge=0, le=5)
    overall_score: float = Field(ge=0.0, le=5.0)


class AnalysisNotes(BaseModel):
    """Detailed explanations for each MEDDPICC dimension."""

    metrics: str
    economic_buyer: str
    decision_criteria: str
    decision_process: str
    paper_process: str
    identify_pain: str
    champion: str
    competition: str


class CallAnalysis(BaseModel):
    """Complete analysis result for a single call."""

    call_id: str
    call_title: str
    gong_link: str
    call_date: datetime
    sales_rep_email: str
    participants: Participants
    is_discovery_call: bool
    discovery_reasoning: Optional[str] = None  # Why it is/isn't a discovery call
    meddpicc_scores: Optional[MEDDPICCScores] = None
    meddpicc_summary: Optional[str] = None  # Overall MEDDPICC summary
    analysis_notes: Optional[AnalysisNotes] = None
    analysis_timestamp: datetime = Field(default_factory=datetime.now)


class AccountCall(BaseModel):
    """Single discovery call record for an account."""

    call_id: str
    call_date: datetime
    sales_rep: str
    external_participants: list[str]
    meddpicc_scores: MEDDPICCScores
    meddpicc_summary: Optional[str] = None  # Overall summary
    analysis_notes: Optional[AnalysisNotes] = None  # Detailed reasoning per dimension


class AccountRecord(BaseModel):
    """Account record with all discovery calls and aggregated MEDDPICC."""

    domain: str
    created_at: datetime
    updated_at: datetime
    calls: list[AccountCall]
    overall_meddpicc: MEDDPICCScores
