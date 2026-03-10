"""Stage classifier service to determine which stage a call belongs to."""

import json
from typing import Dict, Any

from ..core.llm_client import LLMClient
from ..domain import StageClassificationResult


class StageClassifier:
    """Classifies calls into sales stages: discovery, trial, negotiation, or closed."""

    def __init__(self, llm_client: LLMClient):
        """
        Initialize stage classifier.

        Args:
            llm_client: LLM client for API calls
        """
        self.llm_client = llm_client

    def classify_stage(self, transcript: str, call_title: str = "") -> StageClassificationResult:
        """
        Classify the stage of a sales call.

        Args:
            transcript: Full call transcript
            call_title: Optional call title for context

        Returns:
            StageClassificationResult with primary_stage, confidence, and optional secondary_stage
        """
        prompt = self._build_classification_prompt(transcript, call_title)

        response = self.llm_client.call_llm(
            prompt=prompt,
            system_message="You are a sales methodology expert specializing in deal stage classification.",
        )

        return self._parse_classification_response(response)

    def _build_classification_prompt(self, transcript: str, call_title: str) -> str:
        """Build the classification prompt."""
        context = f"Call Title: {call_title}\n\n" if call_title else ""

        return f"""{context}Based on the following sales call transcript, classify which stage of the sales cycle this call represents.

STAGE DEFINITIONS:

**Discovery** - Exploratory conversations and trial preparation:
- Understanding customer's business, challenges, and goals
- Identifying pain points and needs
- Discussing potential solutions at a high level
- Qualifying the opportunity (MEDDPICC)
- Building relationships with stakeholders
- Exploring metrics that matter to them
- Understanding decision-making process and criteria
- Product demonstrations or technical deep dives
- **Trial planning and preparation** (scoping POC, discussing what to test)
- **Setup discussions** (architecture, networking, connectivity, infrastructure)
- **Technical requirements gathering** for trial
- Configuring environments or access for trial
- Planning success criteria for evaluation

KEY: Discovery includes ALL preparatory work BEFORE the customer starts actively using the product.

**Trial** - Customer is actively evaluating the product (MUST be hands-on usage):
- **Customer is actively using/testing the product** (this is required!)
- Progress check-ins during active trial period
- Technical validation based on actual hands-on usage
- User feedback and adoption during active trial
- Discussing results, metrics, or outcomes from their testing
- Troubleshooting issues encountered during active use
- Integration work during active trial
- Competitive bake-offs (head-to-head product testing)
- Trial results review and readiness to advance

KEY: Trial ONLY applies when customer has started hands-on product evaluation. If they're still planning or setting up, it's Discovery.

**Negotiation** - Commercial and legal discussions:
- Pricing and commercial terms negotiations
- Contract review and legal discussions
- Security and compliance reviews
- Procurement process discussions
- Finalizing implementation timeline
- Executive alignment on deal structure
- Handling final objections or concerns before close

**Closed** - Deal outcome discussions:
- Announcement of deal won or lost
- Post-decision debrief or retrospective
- Discussion of why deal was won/lost
- Competitive factors in final decision
- Lessons learned conversations

TRANSCRIPT:
{transcript}

OUTPUT FORMAT:
Respond in JSON format only:
{{
    "primary_stage": "discovery|trial|negotiation|closed",
    "confidence": 0.0-1.0,
    "secondary_stage": "discovery|trial|negotiation|closed|null",
    "reasoning": "Brief explanation of classification"
}}

INSTRUCTIONS:
1. Classify the PRIMARY stage based on the dominant theme of the conversation
2. Set CONFIDENCE (0-1) based on clarity of stage signals
3. If call spans multiple stages, identify SECONDARY_STAGE (otherwise null)
4. Provide brief REASONING for the classification

Respond with JSON only, no additional text."""

    def _parse_classification_response(self, response: str) -> StageClassificationResult:
        """Parse the LLM response into a StageClassificationResult."""
        try:
            # Extract JSON from response (handle potential markdown code blocks)
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            data = json.loads(response)

            return StageClassificationResult(
                primary_stage=data["primary_stage"],
                confidence=float(data["confidence"]),
                secondary_stage=data.get("secondary_stage"),
                reasoning=data.get("reasoning"),
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Fallback to discovery with low confidence if parsing fails
            print(f"⚠️  Failed to parse stage classification: {e}")
            print(f"Response: {response}")
            return StageClassificationResult(
                primary_stage="discovery",
                confidence=0.3,
                reasoning=f"Classification failed: {str(e)}",
            )
