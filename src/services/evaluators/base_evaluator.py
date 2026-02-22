"""Base evaluator class for all stage-specific evaluators."""

from abc import ABC, abstractmethod
from typing import Any

from ...core.llm_client import LLMClient


class BaseEvaluator(ABC):
    """Base class for stage-specific evaluators."""

    def __init__(self, llm_client: LLMClient):
        """
        Initialize evaluator.

        Args:
            llm_client: LLM client for API calls
        """
        self.llm_client = llm_client

    @abstractmethod
    def evaluate(self, transcript: str, call_context: dict = None) -> Any:
        """
        Evaluate a call transcript.

        Args:
            transcript: Full call transcript
            call_context: Optional context (account info, previous scores, etc.)

        Returns:
            Stage-specific score object
        """
        pass

    @abstractmethod
    def _build_evaluation_prompt(self, transcript: str, call_context: dict) -> str:
        """Build the evaluation prompt for this stage."""
        pass

    @abstractmethod
    def _parse_evaluation_response(self, response: str) -> Any:
        """Parse the LLM response into a score object."""
        pass
