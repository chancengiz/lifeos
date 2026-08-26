"""Backend adapters behind LLMService (SPEC 10).

The tier table names a backend per tier, so switching providers is a YAML edit.
Anthropic text tiers go through the official SDK; litellm covers everything the
Anthropic API does not serve, embeddings above all.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class CompletionResult:
    text: str
    input_tokens: int
    output_tokens: int
    raw: object = field(default=None, repr=False)


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    input_tokens: int


class Backend(Protocol):
    def complete(
        self, model: str, messages: list[dict], max_tokens: int, timeout: float
    ) -> CompletionResult: ...

    def embed(self, model: str, texts: list[str], timeout: float) -> EmbeddingResult: ...


class BackendError(RuntimeError):
    """A backend could not serve the request."""


class AnthropicBackend:
    """Official Anthropic SDK. Credentials resolve from the environment."""

    name = "anthropic"

    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def complete(
        self, model: str, messages: list[dict], max_tokens: int, timeout: float
    ) -> CompletionResult:
        system = None
        chat: list[dict] = []
        for message in messages:
            if message.get("role") == "system":
                system = message["content"]
                continue
            chat.append(message)

        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": chat,
        }
        if system is not None:
            kwargs["system"] = system

        response = self.client.with_options(timeout=timeout).messages.create(**kwargs)
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        return CompletionResult(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            raw=response,
        )

    def embed(self, model: str, texts: list[str], timeout: float) -> EmbeddingResult:
        raise BackendError(
            "the Anthropic API has no embeddings endpoint; route TIER_EMBED "
            "through the litellm backend in config/llm_tiers.yaml"
        )


class LiteLLMBackend:
    """Provider-agnostic router. Imported lazily so it stays an optional install."""

    name = "litellm"

    def _litellm(self):
        try:
            import litellm
        except ImportError as exc:  # pragma: no cover - depends on the install
            raise BackendError(
                "the litellm backend needs the litellm package; "
                "install it or point the tier at another backend"
            ) from exc
        return litellm

    def complete(
        self, model: str, messages: list[dict], max_tokens: int, timeout: float
    ) -> CompletionResult:
        litellm = self._litellm()
        response = litellm.completion(
            model=model, messages=messages, max_tokens=max_tokens, timeout=timeout
        )
        usage = response["usage"]
        return CompletionResult(
            text=response["choices"][0]["message"]["content"],
            input_tokens=usage["prompt_tokens"],
            output_tokens=usage["completion_tokens"],
            raw=response,
        )

    def embed(self, model: str, texts: list[str], timeout: float) -> EmbeddingResult:
        litellm = self._litellm()
        response = litellm.embedding(model=model, input=texts, timeout=timeout)
        return EmbeddingResult(
            vectors=[item["embedding"] for item in response["data"]],
            input_tokens=response.get("usage", {}).get("prompt_tokens", 0),
        )


_REGISTRY: dict[str, Backend] = {}


def get_backend(name: str) -> Backend:
    if name not in _REGISTRY:
        if name == AnthropicBackend.name:
            _REGISTRY[name] = AnthropicBackend()
        elif name == LiteLLMBackend.name:
            _REGISTRY[name] = LiteLLMBackend()
        else:
            raise BackendError(f"unknown backend '{name}'")
    return _REGISTRY[name]


def register_backend(name: str, backend: Backend) -> None:
    """Used by tests and by anyone adding a provider without touching LLMService."""
    _REGISTRY[name] = backend


def reset_backends() -> None:
    _REGISTRY.clear()
