"""Gong API client for fetching call transcripts."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urljoin

import httpx

from .config import Settings
from .models import Participants


class GongAPIError(RuntimeError):
    """Raised for non-retryable HTTP errors from Gong API."""


class AsyncGongClient:
    """
    Async Gong API client using httpx.
    - Auth: Basic (Access Key / Secret)
    - Pagination: auto-follow cursor
    - Retries: 429 & 5xx with exponential backoff
    """

    def __init__(
        self,
        settings: Settings,
        *,
        timeout: float = 30.0,
        max_retries: int = 5,
        backoff_factor: float = 0.8,
        default_limit: int = 200,
    ) -> None:
        """Initialize the async Gong client."""
        api_endpoint = settings.gong_api_url
        if not api_endpoint.startswith("http"):
            raise ValueError("gong_api_url must include scheme, e.g. https://...")

        self.base_url = api_endpoint.rstrip("/") + "/"
        self.lookback_days = settings.gong_lookback_days
        self.internal_domain = settings.internal_domain
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.default_limit = default_limit

        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            auth=(settings.gong_access_key, settings.gong_secret_key),
        )

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncGongClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def list_users(self) -> list[dict[str, Any]]:
        """Fetch all Gong users."""
        data = await self._api_call(
            "/v2/users",
            "GET",
            query={"limit": self.default_limit},
        )
        return data.get("users", [])

    async def get_user_ids_for_emails(
        self, emails: list[str]
    ) -> dict[str, str]:
        """
        Map email addresses to Gong user IDs.

        Args:
            emails: List of email addresses

        Returns:
            Dictionary mapping email -> user_id
        """
        targets = {e.strip().lower() for e in emails if e and e.strip()}
        email_to_id: dict[str, str] = {}
        users = await self.list_users()

        for u in users:
            email = (u.get("emailAddress") or u.get("email") or "").strip().lower()
            if email in targets:
                email_to_id[email] = u.get("id")

        return email_to_id

    async def get_calls_for_sales_reps(
        self, sales_rep_emails: list[str], include_all_fields: bool = False
    ) -> list[dict[str, Any]]:
        """
        Fetch calls for specified sales reps with external participants.

        Args:
            sales_rep_emails: List of sales rep email addresses
            include_all_fields: If True, request all available fields from Gong API

        Returns:
            List of call dictionaries with metadata and participants
        """
        # Map emails to user IDs
        email_to_id = await self.get_user_ids_for_emails(sales_rep_emails)
        if not email_to_id:
            return []

        primary_user_ids = list(email_to_id.values())

        # Calculate date range
        to_dt = datetime.now(timezone.utc)
        from_dt = to_dt - timedelta(days=self.lookback_days)

        # Fetch calls - build payload matching Gong API spec
        payload = {
            "filter": {
                "fromDateTime": from_dt.isoformat().replace("+00:00", "Z"),
                "toDateTime": to_dt.isoformat().replace("+00:00", "Z"),
                "primaryUserIds": primary_user_ids,
            },
            "limit": self.default_limit,
        }

        # Always request parties (required for external participant filtering)
        # We can add more fields here as needed
        payload["contentSelector"] = {
            "exposedFields": {
                "parties": True,
            }
        }

        calls = await self._api_call(
            "/v2/calls/extensive",
            "POST",
            payload=payload,
            paginate=True,
        )

        all_calls = calls.get("calls", [])

        # Filter for calls with external participants only
        filtered_calls = []
        id_to_email = {v: k for k, v in email_to_id.items()}

        for call in all_calls:
            if self._has_external_participants(call):
                # Enrich with sales rep email
                meta = call.get("metaData", {})
                primary_user_id = meta.get("primaryUserId")
                call["sales_rep_email"] = id_to_email.get(primary_user_id, "")
                filtered_calls.append(call)

        return filtered_calls

    async def get_transcripts(
        self, call_ids: list[str], chunk_size: int = 50
    ) -> dict[str, str]:
        """
        Fetch transcripts for multiple calls.

        Args:
            call_ids: List of call IDs
            chunk_size: Number of calls per batch request

        Returns:
            Dictionary mapping call_id -> transcript text
        """
        path = "/v2/calls/transcript"
        transcripts: dict[str, str] = {}

        for i in range(0, len(call_ids), chunk_size):
            batch = call_ids[i:i + chunk_size]

            # Build payload with filter structure (some Gong APIs expect this)
            payload = {
                "filter": {
                    "callIds": batch
                }
            }

            data = await self._api_call(
                path,
                "POST",
                payload=payload,
                paginate=True,  # Follow pagination to get all transcripts
            )

            print(f"\n[DEBUG] Transcript API response keys: {list(data.keys())}")

            # Try different possible response structures
            transcript_list = data.get("callTranscripts", []) or data.get("transcripts", [])
            print(f"[DEBUG] Found {len(transcript_list)} transcripts in response")

            for t in transcript_list:
                call_id = t.get("callId")
                print(f"[DEBUG] Processing transcript for call {call_id}")
                print(f"[DEBUG] Transcript object keys: {list(t.keys())}")

                # Try both "sentences" and "transcript" keys (Gong API varies)
                transcript_segments = t.get("sentences") or t.get("transcript", [])
                print(f"[DEBUG] Found {len(transcript_segments)} transcript segments")

                # Combine all sentences into text
                text_parts = []
                for segment in transcript_segments:
                    if isinstance(segment, dict):
                        speaker_id = segment.get("speakerId", "Unknown")
                        # Each segment has a nested "sentences" array
                        sentences = segment.get("sentences", [])

                        for sentence in sentences:
                            if isinstance(sentence, dict):
                                text = sentence.get("text", "")
                                if text:
                                    text_parts.append(f"[{speaker_id}]: {text}")

                transcripts[call_id] = "\n".join(text_parts)
                print(f"[DEBUG] Final transcript length for {call_id}: {len(transcripts[call_id])} chars")

                if call_id:
                    print(f"[DEBUG] Transcript length for {call_id}: {len(transcripts[call_id])} chars")

        return transcripts

    def _has_external_participants(self, call: dict[str, Any]) -> bool:
        """Check if call has any external participants."""
        parties = call.get("parties", [])
        return any(self._is_external_party(p) for p in parties)

    def _is_external_party(self, party: dict[str, Any]) -> bool:
        """
        Determine if a party is external.

        External if:
          - affiliation == 'External', OR
          - affiliation == 'Unknown' AND email domain != internal_domain
        """
        aff = (party.get("affiliation") or "").strip()
        email = (party.get("emailAddress") or "").strip().lower()

        if aff == "External":
            return True

        if aff == "Unknown" and email and "@" in email:
            domain = email.split("@")[-1]
            return domain != self.internal_domain.lower()

        return False

    def extract_participants(self, call: dict[str, Any]) -> Participants:
        """Extract and classify participants from a call."""
        internal = []
        external = []

        for party in call.get("parties", []):
            email = party.get("emailAddress")
            if not email:
                continue

            if self._is_external_party(party):
                external.append(email)
            else:
                internal.append(email)

        return Participants(internal=internal, external=external)

    async def _api_call(
        self,
        api_path: str,
        method: str,
        *,
        payload: Optional[dict[str, Any]] = None,
        query: Optional[dict[str, Any]] = None,
        paginate: bool = True,
    ) -> dict[str, Any]:
        """
        Generic API call with retries and pagination.

        Args:
            api_path: API endpoint path
            method: HTTP method (GET or POST)
            payload: Request body for POST
            query: Query parameters for GET
            paginate: Whether to follow pagination cursors

        Returns:
            API response data
        """
        if not api_path.startswith("/"):
            api_path = "/" + api_path
        url = urljoin(self.base_url, api_path.lstrip("/"))

        body = dict(payload or {})
        params = dict(query or {})
        aggregated: dict[str, Any] = {}
        cursor: Optional[str] = None

        while True:
            if cursor:
                if method.upper() == "GET":
                    params["cursor"] = cursor
                else:
                    body["cursor"] = cursor

            resp_json = await self._request_with_retries(
                url=url,
                method=method,
                body=body if method.upper() != "GET" else None,
                params=params if method.upper() == "GET" else None,
            )

            if not paginate:
                return resp_json

            # Aggregate array fields
            for k, v in resp_json.items():
                if isinstance(v, list):
                    aggregated.setdefault(k, []).extend(v)
                else:
                    aggregated[k] = v

            # Check for next page
            records = resp_json.get("records", {})
            cursor = records.get("cursor") if isinstance(records, dict) else resp_json.get("cursor")

            if not cursor:
                return aggregated

    async def _request_with_retries(
        self,
        *,
        url: str,
        method: str,
        body: Optional[dict[str, Any]],
        params: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """Make HTTP request with retry logic."""
        import asyncio

        attempt = 0
        while True:
            try:
                resp = await self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    content=None if body is None else json.dumps(body),
                )
            except httpx.RequestError as e:
                if attempt >= self.max_retries:
                    raise GongAPIError(f"Request failed after retries: {e}") from e
                await asyncio.sleep(self._backoff_sleep(attempt))
                attempt += 1
                continue

            # Retry on rate limit or server errors
            if resp.status_code in (429, 500, 502, 503, 504):
                if attempt >= self.max_retries:
                    raise GongAPIError(f"HTTP {resp.status_code}: {resp.text}")
                await asyncio.sleep(self._backoff_sleep(attempt))
                attempt += 1
                continue

            # Non-success
            if resp.status_code >= 400:
                raise GongAPIError(f"HTTP {resp.status_code}: {resp.text}")

            try:
                return resp.json()
            except ValueError as e:
                raise GongAPIError(f"Invalid JSON response: {e}") from e

    def _backoff_sleep(self, attempt: int) -> float:
        """Calculate exponential backoff sleep time."""
        base = (2 ** attempt) * self.backoff_factor
        return min(base, 30.0)
