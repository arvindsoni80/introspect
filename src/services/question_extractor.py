"""Question Extractor - Extract questions from call transcripts by speaker.

This module provides functionality to identify and extract questions asked by
participants in sales calls, enabling persona-based question analysis.
"""

import json
import re
from typing import Dict, List, Optional
from ..core.llm_client import LLMClient


class QuestionExtractor:
    """Extracts questions from transcripts and attributes them to speakers."""

    def __init__(self, llm_client: LLMClient):
        """
        Initialize question extractor.

        Args:
            llm_client: LLM client for question extraction
        """
        self.llm_client = llm_client

    def extract_questions_for_call(
        self,
        transcript: str,
        participants: Dict[str, Dict]
    ) -> Dict[str, List[str]]:
        """
        Extract questions from a call transcript and attribute to speakers.

        Args:
            transcript: Full call transcript (preferably enriched with speaker labels)
            participants: Dict of participant info by speaker_id
                         {speaker_id: {name: ..., title: ..., affiliation: ...}}

        Returns:
            Dict mapping speaker_id to list of questions they asked
            Example: {"speaker_1": ["What's the pricing?", "How does it scale?"]}
        """
        if not transcript or not participants:
            return {}

        # Filter to external participants only (customers)
        external_participants = {
            speaker_id: info
            for speaker_id, info in participants.items()
            if info.get('affiliation') == 'External'
        }

        if not external_participants:
            return {}

        # Extract questions using LLM
        questions_by_speaker = self._extract_with_llm(transcript, external_participants)

        return questions_by_speaker

    def _extract_with_llm(
        self,
        transcript: str,
        participants: Dict[str, Dict]
    ) -> Dict[str, List[str]]:
        """
        Use LLM to extract questions from transcript.

        Args:
            transcript: Full transcript text
            participants: External participants only

        Returns:
            Dict of speaker_id to list of questions
        """
        # Build participant list for prompt
        participant_list = []
        for speaker_id, info in participants.items():
            name = info.get('name', 'Unknown')
            title = info.get('title', '')
            participant_list.append(f"- {name} ({title})" if title else f"- {name}")

        participants_str = "\n".join(participant_list)

        # Construct prompt
        prompt = f"""You are analyzing a sales call transcript. Extract ONLY substantive business and product questions asked by the customer.

CUSTOMER PARTICIPANTS:
{participants_str}

EXTRACT ONLY questions about:
- Product features, capabilities, functionality
- Technical details, integrations, APIs, architecture
- Pricing, licensing, commercial terms, contracts
- Use cases, workflows, implementation approach
- Customer proof points, case studies, references, ROI
- Security, compliance, data privacy, certifications
- Competitive differentiation, alternatives comparison
- Support, SLAs, professional services
- Roadmap, future features, timelines

DO NOT EXTRACT these types of questions (CRITICAL):
- Meeting logistics: "Who else is joining?", "Are you expecting someone?"
- Audio/video checks: "Can you hear me?", "Is my screen visible?", "Is it okay now?"
- Scheduling: "When can we meet?", "What time works?"
- Introductions: "Should I introduce myself?", "Who are you?"
- Clarifications: "What did you say?", "Can you repeat that?"
- Social: "How are you?", "How's the weather?"
- Incomplete fragments: "So...", "What about..."

EXAMPLES OF GOOD QUESTIONS TO EXTRACT:
✓ "What's your pricing model for enterprise deployments?"
✓ "How does this integrate with our CI/CD pipeline?"
✓ "Do you have SOC 2 compliance?"
✓ "What's the implementation timeline?"
✓ "Can you share customer references in the financial sector?"

EXAMPLES OF BAD QUESTIONS TO EXCLUDE:
✗ "Can you hear me properly?"
✗ "Are you expecting someone from your end to join?"
✗ "Is it okay now?"
✗ "Should I share my screen?"

Clean up questions (remove "um", "uh", "like"). Return JSON format:
{{
  "Person Name": ["question 1", "question 2"],
  "Another Person": ["question 3"]
}}

TRANSCRIPT:
{transcript}

Return ONLY the JSON object."""

        try:
            # Call LLM
            response = self.llm_client.call_llm(prompt, max_tokens=2000)

            # Parse JSON response
            # Clean up response (remove markdown code blocks if present)
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            questions_by_name = json.loads(response)

            # Map from name back to speaker_id
            questions_by_speaker = {}
            name_to_id = {
                info.get('name', '').lower(): speaker_id
                for speaker_id, info in participants.items()
            }

            for name, questions in questions_by_name.items():
                # Try to match name to speaker_id (case-insensitive)
                name_lower = name.lower().strip()
                speaker_id = None

                # Exact match
                if name_lower in name_to_id:
                    speaker_id = name_to_id[name_lower]
                else:
                    # Partial match (first name or last name)
                    for participant_name, sid in name_to_id.items():
                        if name_lower in participant_name or participant_name in name_lower:
                            speaker_id = sid
                            break

                if speaker_id and questions:
                    questions_by_speaker[speaker_id] = questions

            return questions_by_speaker

        except json.JSONDecodeError as e:
            print(f"⚠️  Failed to parse LLM response as JSON: {e}")
            print(f"   Response: {response[:200]}...")
            return {}
        except Exception as e:
            print(f"⚠️  Error extracting questions: {e}")
            return {}

    def count_questions(self, questions: List[str]) -> int:
        """
        Count number of questions in a list.

        Args:
            questions: List of question strings

        Returns:
            Number of questions
        """
        return len(questions) if questions else 0

    def format_questions_for_storage(self, questions: List[str]) -> str:
        """
        Format questions as JSON string for database storage.

        Args:
            questions: List of question strings

        Returns:
            JSON string representation
        """
        return json.dumps(questions) if questions else None

    def parse_questions_from_storage(self, questions_json: str) -> List[str]:
        """
        Parse questions from JSON string stored in database.

        Args:
            questions_json: JSON string from database

        Returns:
            List of questions
        """
        if not questions_json:
            return []

        try:
            return json.loads(questions_json)
        except json.JSONDecodeError:
            return []
