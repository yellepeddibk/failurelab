"""Network-free tests for the Ollama adapter.

Every test mocks the HTTP boundary (``urllib.request.urlopen``). No test opens a
socket, and the default mock raises if a second request is attempted.
"""

from __future__ import annotations

import json
import traceback
import urllib.error
import urllib.request

import pytest

import failurelab as fl
from failurelab.llm import OllamaProvider, ollama
from failurelab.llm.errors import ProviderError, SanitizedProviderError
from failurelab.llm.ollama import DEFAULT_HOST, MAX_RESPONSE_BYTES, RESPONSE_SCHEMA
from failurelab.llm.protocol import InterpretationRequest

SECRET = "sk-must-not-surface"

VALID_INTERPRETATION = {
    "summary": {"text": "ok", "evidence": [{"kind": "metric", "id": "failure_rate"}]},
    "observations": [
        {"statement": "grounded", "evidence": [{"kind": "metric", "id": "failure_rate"}]}
    ],
    "caveats": ["c"],
}

OLLAMA_OK = {
    "model": "test-model",
    "message": {"role": "assistant", "content": json.dumps(VALID_INTERPRETATION)},
    "done": True,
    "prompt_eval_count": 123,
    "eval_count": 45,
}


class _FakeHTTPResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, amt: int | None = None) -> bytes:
        return self._body if amt is None else self._body[:amt]


def _install(monkeypatch, *, body=None, error=None):
    """Patch urlopen; returns a dict capturing the single request."""
    captured: dict = {"calls": 0}

    def fake_urlopen(request, timeout=None):
        captured["calls"] += 1
        if captured["calls"] > 1:
            raise AssertionError("adapter issued more than one HTTP request")
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = {k.lower(): v for k, v in request.headers.items()}
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        if error is not None:
            raise error
        payload = OLLAMA_OK if body is None else body
        raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        return _FakeHTTPResponse(raw)

    monkeypatch.setattr(ollama._OPENER, "open", fake_urlopen)
    return captured


def _request() -> InterpretationRequest:
    return InterpretationRequest(
        system="SYSTEM",
        evidence={"metrics": {"failure_rate": {"value": 1.0}}},
        parameters={"max_output_tokens": 256, "timeout": 12.5},
    )


def _analysis_report() -> fl.AnalysisReport:
    return fl.analyze(
        [
            {
                "schema_version": "0.1",
                "trace_id": "t1",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "success": False,
                "query": "q",
                "failure_type": "retrieval_failure",
            }
        ],
        strict=False,
    )


# --- construction ------------------------------------------------------------


def test_construction_makes_no_network_call(monkeypatch) -> None:
    captured = _install(monkeypatch)
    OllamaProvider(model="gemma3")
    assert captured["calls"] == 0
    assert OllamaProvider(model="gemma3").host == DEFAULT_HOST


def test_env_vars_do_not_configure_or_activate(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", SECRET)
    monkeypatch.setenv("OLLAMA_HOST", "http://evil.example")
    captured = _install(monkeypatch)
    provider = OllamaProvider(model="gemma3")
    assert provider.host == DEFAULT_HOST  # env never consulted
    provider.generate(_request())
    assert captured["url"].startswith(DEFAULT_HOST)
    assert SECRET not in json.dumps(captured["payload"])
    assert "authorization" not in captured["headers"]


# --- request construction ----------------------------------------------------


def test_request_shape_and_bounds(monkeypatch) -> None:
    captured = _install(monkeypatch)
    OllamaProvider(model="gemma3").generate(_request())

    assert captured["calls"] == 1  # exactly one HTTP request
    assert captured["url"] == f"{DEFAULT_HOST}/api/chat"
    assert captured["method"] == "POST"
    assert captured["headers"]["content-type"] == "application/json"
    assert captured["timeout"] == 12.5  # timeout propagated

    payload = captured["payload"]
    assert payload["model"] == "gemma3"
    assert payload["stream"] is False
    assert payload["format"] == RESPONSE_SCHEMA  # complete JSON schema
    assert payload["options"]["temperature"] == 0
    assert payload["options"]["num_predict"] == 256  # max_output_tokens mapped
    assert payload["messages"][0] == {"role": "system", "content": "SYSTEM"}
    assert payload["messages"][1]["role"] == "user"
    assert "failure_rate" in payload["messages"][1]["content"]


def test_host_normalization_with_trailing_slash(monkeypatch) -> None:
    captured = _install(monkeypatch)
    OllamaProvider(model="gemma3", host="http://localhost:11434/").generate(_request())
    assert captured["url"] == "http://localhost:11434/api/chat"


# --- response mapping --------------------------------------------------------


def test_response_and_usage_mapping(monkeypatch) -> None:
    _install(monkeypatch)
    response = OllamaProvider(model="gemma3").generate(_request())
    assert response.text == json.dumps(VALID_INTERPRETATION)
    assert response.model == "test-model"
    assert response.token_usage == {"input_tokens": 123, "output_tokens": 45}


def test_usage_absent_when_counts_missing(monkeypatch) -> None:
    _install(monkeypatch, body={"model": "m", "message": {"content": "{}"}})
    response = OllamaProvider(model="gemma3").generate(_request())
    assert response.token_usage is None


# --- error behavior ----------------------------------------------------------


def test_connection_failure_is_actionable(monkeypatch) -> None:
    _install(monkeypatch, error=urllib.error.URLError("connection refused"))
    with pytest.raises(ProviderError) as excinfo:
        OllamaProvider(model="gemma3").generate(_request())
    assert "Could not connect to Ollama" in str(excinfo.value)


def test_timeout_is_actionable(monkeypatch) -> None:
    _install(monkeypatch, error=TimeoutError("timed out"))
    with pytest.raises(ProviderError) as excinfo:
        OllamaProvider(model="gemma3").generate(_request())
    assert "timed out" in str(excinfo.value)


def test_missing_model_404_suggests_pull(monkeypatch) -> None:
    _install(
        monkeypatch,
        error=urllib.error.HTTPError(url="u", code=404, msg=SECRET, hdrs=None, fp=None),
    )
    with pytest.raises(ProviderError) as excinfo:
        OllamaProvider(model="gemma3").generate(_request())
    message = str(excinfo.value)
    assert "ollama pull gemma3" in message
    assert SECRET not in message


def test_generic_http_error_is_sanitized(monkeypatch) -> None:
    _install(
        monkeypatch,
        error=urllib.error.HTTPError(url="u", code=500, msg=SECRET, hdrs=None, fp=None),
    )
    with pytest.raises(ProviderError) as excinfo:
        OllamaProvider(model="gemma3").generate(_request())
    message = str(excinfo.value)
    assert "HTTP status 500" in message
    assert SECRET not in message


def test_malformed_json_response(monkeypatch) -> None:
    _install(monkeypatch, body=b"not json at all")
    with pytest.raises(ProviderError) as excinfo:
        OllamaProvider(model="gemma3").generate(_request())
    assert "malformed JSON" in str(excinfo.value)


def test_missing_message_content(monkeypatch) -> None:
    _install(monkeypatch, body={"model": "m", "done": True})
    with pytest.raises(ProviderError) as excinfo:
        OllamaProvider(model="gemma3").generate(_request())
    assert "no message content" in str(excinfo.value)


def test_http_error_secret_absent_from_traceback(monkeypatch) -> None:
    _install(
        monkeypatch,
        error=urllib.error.HTTPError(url="u", code=500, msg=SECRET, hdrs=None, fp=None),
    )
    formatted = ""
    try:
        OllamaProvider(model="gemma3").generate(_request())
    except ProviderError as error:
        formatted = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    assert formatted
    assert SECRET not in formatted


# --- configuration validation (network-free) --------------------------------


@pytest.mark.parametrize(
    "host",
    [
        "ftp://localhost:11434",  # wrong scheme
        "localhost:11434",  # no scheme
        "http://",  # no hostname
        "http://localhost:11434?a=1",  # query
        "http://localhost:11434#frag",  # fragment
        "http://localhost:11434/v1/chat",  # non-root path
        "",  # empty
    ],
)
def test_invalid_host_rejected_at_construction(host: str) -> None:
    with pytest.raises(ValueError):
        OllamaProvider(model="gemma3", host=host)


@pytest.mark.parametrize("model", ["", "   ", "bad\nmodel"])
def test_invalid_model_rejected_at_construction(model: str) -> None:
    with pytest.raises(ValueError):
        OllamaProvider(model=model)


def test_credentials_in_host_rejected_and_absent_from_traceback() -> None:
    formatted = ""
    try:
        OllamaProvider(model="gemma3", host=f"https://user:{SECRET}@example.com")
    except ValueError as error:
        formatted = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    assert formatted
    assert SECRET not in formatted  # credential-bearing host never echoed


def test_valid_host_normalized_once() -> None:
    assert OllamaProvider(model="gemma3", host="http://localhost:11434/").host == DEFAULT_HOST
    assert OllamaProvider(model=" gemma3 ").model == "gemma3"


# --- transport restriction ---------------------------------------------------


def test_opener_handles_only_http_and_https() -> None:
    """The restricted opener cannot read file:, ftp:, or data: URLs."""
    schemes = set(ollama._OPENER.handle_open)
    assert schemes == {"http", "https", "unknown"}
    assert "file" not in schemes
    assert "ftp" not in schemes
    assert "data" not in schemes


# --- response size bound -----------------------------------------------------


def test_oversized_response_rejected(monkeypatch) -> None:
    _install(monkeypatch, body=b"x" * (MAX_RESPONSE_BYTES + 10))
    with pytest.raises(SanitizedProviderError) as excinfo:
        OllamaProvider(model="gemma3").generate(_request())
    assert "larger than the supported limit" in str(excinfo.value)


# --- integration with interpret ---------------------------------------------


def test_interpret_passes_sanitized_provider_error_through(monkeypatch) -> None:
    _install(monkeypatch, error=urllib.error.URLError("refused"))
    report = _analysis_report()
    with pytest.raises(ProviderError) as excinfo:
        fl.interpret(report, provider=OllamaProvider(model="gemma3"))
    # the adapter's actionable message survives, not a generic wrapper
    assert "Could not connect to Ollama" in str(excinfo.value)


def test_plain_provider_error_cannot_bypass_sanitization() -> None:
    """A third-party provider must not leak by raising a bare ProviderError."""

    class _LeakyProvider:
        name = "leaky"

        def generate(self, request):
            raise ProviderError(f"API key: {SECRET}")

    formatted = ""
    try:
        fl.interpret(_analysis_report(), provider=_LeakyProvider())
    except ProviderError as error:
        formatted = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    assert formatted
    assert SECRET not in formatted  # generically wrapped, chain suppressed
    assert "failed to generate a response" in formatted


def test_interpret_end_to_end_with_mocked_ollama(monkeypatch) -> None:
    captured = _install(monkeypatch)
    report = _analysis_report()
    interp = fl.interpret(report, provider=OllamaProvider(model="gemma3"))
    assert captured["calls"] == 1
    assert interp.summary == "ok"
    assert interp.summary_evidence
    assert [o.statement for o in interp.observations] == ["grounded"]
    assert interp.generation_metadata.provider == "ollama"
    assert interp.generation_metadata.model == "test-model"
    assert interp.generation_metadata.token_usage == {"input_tokens": 123, "output_tokens": 45}
