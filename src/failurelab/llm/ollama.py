"""Local Ollama provider adapter.

Targets a local or self-hosted Ollama server. Uses only the Python standard
library, so installing FailureLab adds no dependency for this adapter. The
Ollama runtime and the model itself remain separate prerequisites that you
install and pull yourself.

The adapter reads no environment variable (notably not ``OLLAMA_API_KEY``),
loads no ``.env`` file, performs no network activity at import or construction,
makes no preflight or model-listing request, never pulls a model, never retries,
and never streams. One ``generate`` call issues exactly one HTTP request.

Errors are actionable but sanitized: they name the host, model, and HTTP status
only. Response bodies, server messages, credentials, prompts, evidence, and
generated content are never placed into exceptions.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from failurelab.llm.errors import SanitizedProviderError
from failurelab.llm.protocol import InterpretationRequest, ProviderResponse
from failurelab.llm.schema import RESPONSE_SCHEMA
from failurelab.utilities.serialization import stable_dumps

__all__ = ["DEFAULT_HOST", "MAX_RESPONSE_BYTES", "RESPONSE_SCHEMA", "OllamaProvider"]

DEFAULT_HOST = "http://localhost:11434"
MAX_RESPONSE_BYTES = 1_048_576


def _build_restricted_opener() -> urllib.request.OpenerDirector:
    """Build an opener that can only speak HTTP and HTTPS.

    The generic ``urlopen`` entry point also understands ``file:``, ``ftp:``, and
    ``data:`` URLs. Restricting the handler set means a misconfigured host cannot
    be used to read a local file, which complements the scheme validation applied
    when a provider is constructed. Proxy and redirect handlers are deliberately
    omitted: requests target a local or self-hosted server, and a redirect is
    reported as an HTTP status rather than being followed.
    """
    opener = urllib.request.OpenerDirector()
    opener.add_handler(urllib.request.HTTPHandler())
    opener.add_handler(urllib.request.HTTPSHandler())
    opener.add_handler(urllib.request.HTTPDefaultErrorHandler())
    opener.add_handler(urllib.request.HTTPErrorProcessor())
    opener.add_handler(urllib.request.UnknownHandler())
    return opener


_OPENER = _build_restricted_opener()


def _as_number(value: object, default: float) -> float:
    """Read a numeric execution bound, falling back when absent or non-numeric."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _has_control_characters(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _normalize_host(host: str) -> str:
    """Validate and normalize a host without contacting it.

    Error messages deliberately exclude the host value so a credential-bearing
    URL cannot leak through an exception.
    """
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host must be a non-empty string")
    candidate = host.strip().rstrip("/")
    if _has_control_characters(candidate):
        raise ValueError("host must not contain control characters")

    parts = urllib.parse.urlsplit(candidate)
    if parts.scheme not in ("http", "https"):
        raise ValueError("host must use the http or https scheme")
    if not parts.hostname:
        raise ValueError("host must include a hostname")
    if parts.username or parts.password:
        raise ValueError("host must not embed a username or password")
    if parts.query or parts.fragment:
        raise ValueError("host must not contain a query string or fragment")
    if parts.path not in ("", "/"):
        raise ValueError("host must not contain a path")
    return candidate


@dataclass(slots=True)
class OllamaProvider:
    """Interpretation provider backed by a local or self-hosted Ollama server.

    ``model`` must be explicitly supplied and already pulled, for example with
    ``ollama pull gemma3``. Constructing this object performs no network call.

    Pointing ``host`` away from localhost transmits the structured evidence to
    that machine or service.
    """

    model: str
    host: str = DEFAULT_HOST
    name: str = "ollama"

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be a non-empty string")
        if _has_control_characters(self.model):
            raise ValueError("model must not contain control characters")
        self.model = self.model.strip()
        self.host = _normalize_host(self.host)

    def generate(self, request: InterpretationRequest) -> ProviderResponse:
        base = self.host
        url = f"{base}/api/chat"
        timeout = _as_number(request.parameters.get("timeout"), 30.0)
        num_predict = int(_as_number(request.parameters.get("max_output_tokens"), 1024))

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": stable_dumps(request.evidence)},
            ],
            "stream": False,
            "format": RESPONSE_SCHEMA,
            "options": {"temperature": 0, "num_predict": num_predict},
        }
        http_request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with _OPENER.open(http_request, timeout=timeout) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            status = error.code
            if status == 404:
                raise SanitizedProviderError(
                    f"Ollama model {self.model!r} was not found at {base}. "
                    f"Run: ollama pull {self.model}"
                ) from None
            raise SanitizedProviderError(
                f"Ollama request to {base} failed with HTTP status {status}."
            ) from None
        except TimeoutError:
            raise SanitizedProviderError(
                f"Ollama request to {base} timed out after {timeout} seconds."
            ) from None
        except urllib.error.URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise SanitizedProviderError(
                    f"Ollama request to {base} timed out after {timeout} seconds."
                ) from None
            raise SanitizedProviderError(
                f"Could not connect to Ollama at {base}. Install or start Ollama, then retry."
            ) from None

        if len(body) > MAX_RESPONSE_BYTES:
            raise SanitizedProviderError(
                f"Ollama at {base} returned a response larger than the supported limit "
                f"({MAX_RESPONSE_BYTES} bytes)."
            )
        return self._build_response(body, base)

    def _build_response(self, body: bytes, base: str) -> ProviderResponse:
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise SanitizedProviderError(
                f"Ollama at {base} returned a malformed JSON response."
            ) from None
        if not isinstance(parsed, dict):
            raise SanitizedProviderError(
                f"Ollama at {base} returned an unexpected response shape."
            ) from None

        message = parsed.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise SanitizedProviderError(
                f"Ollama response from {base} contained no message content."
            ) from None

        usage: dict[str, int] = {}
        prompt_tokens = parsed.get("prompt_eval_count")
        completion_tokens = parsed.get("eval_count")
        if isinstance(prompt_tokens, int):
            usage["input_tokens"] = prompt_tokens
        if isinstance(completion_tokens, int):
            usage["output_tokens"] = completion_tokens

        model = parsed.get("model")
        return ProviderResponse(
            text=content,
            model=model if isinstance(model, str) and model else self.model,
            token_usage=usage or None,
        )
