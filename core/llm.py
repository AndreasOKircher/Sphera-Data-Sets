"""Thin LLM provider abstraction for the Sphera enrichment pipeline."""
from typing import Protocol, runtime_checkable
import anthropic


@runtime_checkable
class LLMClient(Protocol):
    """Minimal interface for LLM text completion."""

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        """Return the model's response as a plain string."""
        ...


class AnthropicLLMClient:
    """LLMClient backed by the Anthropic Messages API.

    Applies cache_control: ephemeral on the system prompt automatically.
    """

    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self._client = client
        self._model = model

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text


def create_llm_client(provider: str, **kwargs) -> LLMClient:
    """Factory for LLM clients.

    Parameters
    ----------
    provider:   "anthropic" or "vio"
    **kwargs:   For "anthropic": api_key, model
                For "vio":       api_key, model, base_url, tenant_id
    """
    if provider == "anthropic":
        client = anthropic.Anthropic(api_key=kwargs["api_key"])
        return AnthropicLLMClient(client=client, model=kwargs["model"])
    raise ValueError(f"unknown LLM provider: {provider!r}. Expected 'anthropic' or 'vio'.")
