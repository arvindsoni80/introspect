"""LLM client for Anthropic API calls."""

from anthropic import Anthropic


class LLMClient:
    """Client for interacting with Anthropic's Claude API."""

    def __init__(self, anthropic_api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        """
        Initialize LLM client.

        Args:
            anthropic_api_key: Anthropic API key
            model: Default Claude model to use
        """
        if not anthropic_api_key:
            raise ValueError("Anthropic API key is required")

        self.anthropic = Anthropic(api_key=anthropic_api_key)
        self.model = model

    def call_llm(
        self,
        prompt: str,
        system_message: str = "",
        model_name: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str:
        """
        Call Anthropic API with prompt.

        Args:
            prompt: User prompt
            system_message: System message (optional)
            model_name: Claude model to use (defaults to model set in __init__)
            temperature: Temperature (0-1)
            max_tokens: Max tokens in response

        Returns:
            LLM response text
        """
        # Use instance model if not specified
        model = model_name or self.model

        response = self.anthropic.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_message if system_message else "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text
