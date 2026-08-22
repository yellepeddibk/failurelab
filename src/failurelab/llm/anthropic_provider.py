"""Anthropic provider adapter.

Requires the optional ``failurelab[anthropic]`` extra. The SDK is imported
lazily, so this module can be imported (and the provider exported) even when the
extra is not installed; constructing a provider without it raises
``MissingLLMDependencyError`` with an install hint.

You bring your own API key. The key is supplied explicitly, or read once from
``ANTHROPIC_API_KEY`` at construction and passed explicitly to the SDK client.
FailureLab never loads ``.env`` files, and deliberately does not let the SDK
resolve ambient credentials of its own (auth tokens or CLI login profiles on
disk), so a request cannot be billed to an account the caller did not name. The
key is never logged, never included in provenance, and never placed in an
exception or ``repr``.

One ``generate`` call issues exactly one Messages API request: no retries, no
streaming, no tool use, and no agent loop. Errors are sanitized: they name the
model and HTTP status only, never response bodies, request content, or
credentials.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from failurelab.llm.errors import MissingLLMDependencyError, SanitizedProviderError
from failurelab.llm.protocol import InterpretationRequest, ProviderResponse
from failurelab.llm.schema import RESPONSE_SCHEMA
from failurelab.utilities.serialization import stable_dumps

API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"
INSTALL_HINT = 'install the optional extra: pip install "failurelab[anthropic]"'


def _as_number(value: object, default: float) -> float:
    """Read a numeric execution bound, falling back when absent or non-numeric."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _has_control_characters(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _load_sdk() -> Any:
    """Import the Anthropic SDK, or explain how to install it."""
    try:
        import anthropic
    except ImportError as error:
        raise MissingLLMDependencyError(
            f"AnthropicProvider requires the 'anthropic' package. {INSTALL_HINT}"
        ) from error
    return anthropic


@dataclass(slots=True)
class AnthropicProvider:
    """Interpretation provider backed by the Anthropic Messages API.

    ``model`` is required and has no library default: naming the model is a cost
    decision that belongs to the caller. Constructing this object performs no
    network call.

    Calling a hosted API transmits the structured evidence to Anthropic. Raw
    content and trace IDs remain excluded unless you opt in through
    ``failurelab.interpret``.
    """

    model: str
    api_key: str | None = field(default=None, repr=False)
    name: str = "anthropic"
    _key: str = field(init=False, repr=False, default="")
    _client: Any = field(init=False, repr=False, default=None)

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be a non-empty string")
        if _has_control_characters(self.model):
            raise ValueError("model must not contain control characters")
        self.model = self.model.strip()

        key = self.api_key if self.api_key is not None else os.environ.get(API_KEY_ENV_VAR)
        if not isinstance(key, str) or not key.strip():
            raise ValueError(
                "an Anthropic API key is required: pass api_key=... or set the "
                f"{API_KEY_ENV_VAR} environment variable"
            )
        self._key = key.strip()
        self.api_key = None  # keep the key only in the private field

    def _ensure_client(self) -> Any:
        """Build the SDK client once. Constructing a client performs no request."""
        if self._client is None:
            sdk = _load_sdk()
            # max_retries=0: the SDK retries twice by default, which would issue
            # additional billable requests behind the single-call guarantee.
            self._client = sdk.Anthropic(api_key=self._key, max_retries=0)
        return self._client

    def generate(self, request: InterpretationRequest) -> ProviderResponse:
        sdk = _load_sdk()
        client = self._ensure_client()
        timeout = _as_number(request.parameters.get("timeout"), 30.0)
        max_tokens = int(_as_number(request.parameters.get("max_output_tokens"), 1024))

        try:
            response = client.with_options(timeout=timeout).messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=request.system,
                messages=[{"role": "user", "content": stable_dumps(request.evidence)}],
                output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
                # Thinking shares the max_tokens budget with the response, so it
                # is disabled for this bounded schema-constrained extraction.
                # Sampling parameters are deliberately absent: current models
                # reject temperature, top_p, and top_k.
                thinking={"type": "disabled"},
            )
        except sdk.AuthenticationError:
            raise SanitizedProviderError(
                "Anthropic rejected the API key. Check the key and its permissions."
            ) from None
        except sdk.PermissionDeniedError:
            raise SanitizedProviderError(
                f"The API key is not permitted to use model {self.model!r}."
            ) from None
        except sdk.NotFoundError:
            raise SanitizedProviderError(f"Anthropic model {self.model!r} was not found.") from None
        except sdk.RateLimitError:
            raise SanitizedProviderError("Anthropic rate limit reached. Retry later.") from None
        except sdk.APITimeoutError:
            raise SanitizedProviderError(
                f"Anthropic request timed out after {timeout} seconds."
            ) from None
        except sdk.APIConnectionError:
            raise SanitizedProviderError(
                "Could not connect to the Anthropic API. Check network connectivity."
            ) from None
        except sdk.APIStatusError as error:
            status = getattr(error, "status_code", "unknown")
            raise SanitizedProviderError(
                f"Anthropic request failed with HTTP status {status}."
            ) from None

        return self._build_response(response)

    def _build_response(self, response: Any) -> ProviderResponse:
        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "refusal":
            raise SanitizedProviderError(
                "Anthropic declined the request. No interpretation was produced."
            )
        if stop_reason == "max_tokens":
            raise SanitizedProviderError(
                "The Anthropic response was truncated by the output limit. "
                "Raise max_output_tokens and retry."
            )

        text = self._first_text(response)
        if not text:
            raise SanitizedProviderError("The Anthropic response contained no text content.")

        usage: dict[str, int] = {}
        raw_usage = getattr(response, "usage", None)
        prompt_tokens = getattr(raw_usage, "input_tokens", None)
        completion_tokens = getattr(raw_usage, "output_tokens", None)
        if isinstance(prompt_tokens, int):
            usage["input_tokens"] = prompt_tokens
        if isinstance(completion_tokens, int):
            usage["output_tokens"] = completion_tokens

        model = getattr(response, "model", None)
        return ProviderResponse(
            text=text,
            model=model if isinstance(model, str) and model else self.model,
            token_usage=usage or None,
        )

    @staticmethod
    def _first_text(response: Any) -> str:
        for block in getattr(response, "content", None) or []:
            if getattr(block, "type", None) == "text":
                text = getattr(block, "text", "")
                if isinstance(text, str) and text.strip():
                    return text
        return ""
