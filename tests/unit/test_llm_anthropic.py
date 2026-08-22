"""Network-free tests for the Anthropic adapter.

The SDK is not installed in CI. Every test injects a fake SDK namespace through
``_load_sdk``, so no test imports ``anthropic``, opens a socket, or spends money.
"""

from __future__ import annotations

import json
import traceback
import types

import pytest

import failurelab as fl
from failurelab.llm import AnthropicProvider, anthropic_provider
from failurelab.llm.errors import MissingLLMDependencyError, SanitizedProviderError
from failurelab.llm.protocol import InterpretationRequest
from failurelab.llm.schema import RESPONSE_SCHEMA

SECRET = "sk-ant-must-not-surface"

VALID_INTERPRETATION = {
    "summary": {"text": "ok", "evidence": [{"kind": "metric", "id": "failure_rate"}]},
    "observations": [
        {"statement": "grounded", "evidence": [{"kind": "metric", "id": "failure_rate"}]}
    ],
    "caveats": ["c"],
}


# --- fake SDK ----------------------------------------------------------------


class _APIStatusError(Exception):
    def __init__(self, message: str = "", status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


class _AuthenticationError(_APIStatusError): ...


class _PermissionDeniedError(_APIStatusError): ...


class _NotFoundError(_APIStatusError): ...


class _RateLimitError(_APIStatusError): ...


class _APITimeoutError(Exception): ...


class _APIConnectionError(Exception): ...


class _Block:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Usage:
    def __init__(self) -> None:
        self.input_tokens = 321
        self.output_tokens = 65


class _Response:
    def __init__(self, text: str, stop_reason: str = "end_turn") -> None:
        self.content = [_Block(text)] if text else []
        self.model = "claude-haiku-4-5-fake"
        self.stop_reason = stop_reason
        self.usage = _Usage()


def _fake_sdk(monkeypatch, *, response=None, error=None):
    """Install a fake SDK; returns a dict capturing the single request."""
    captured: dict = {"calls": 0, "with_options": [], "client_kwargs": None}

    class _Messages:
        def create(self, **kwargs):
            captured["calls"] += 1
            if captured["calls"] > 1:
                raise AssertionError("adapter issued more than one request")
            captured["kwargs"] = kwargs
            if error is not None:
                raise error
            return response if response is not None else _Response(json.dumps(VALID_INTERPRETATION))

    class _Client:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.messages = _Messages()

        def with_options(self, **kwargs):
            captured["with_options"].append(kwargs)
            return self

    sdk = types.SimpleNamespace(
        Anthropic=_Client,
        AuthenticationError=_AuthenticationError,
        PermissionDeniedError=_PermissionDeniedError,
        NotFoundError=_NotFoundError,
        RateLimitError=_RateLimitError,
        APITimeoutError=_APITimeoutError,
        APIConnectionError=_APIConnectionError,
        APIStatusError=_APIStatusError,
    )
    monkeypatch.setattr(anthropic_provider, "_load_sdk", lambda: sdk)
    return captured


def _request() -> InterpretationRequest:
    return InterpretationRequest(
        system="SYSTEM",
        evidence={"metrics": {"failure_rate": {"value": 1.0}}},
        parameters={"max_output_tokens": 1024, "timeout": 12.5},
    )


def _provider() -> AnthropicProvider:
    return AnthropicProvider(model="claude-haiku-4-5", api_key=SECRET)


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


def test_construction_requires_explicit_model() -> None:
    for model in ("", "   ", "bad\nmodel"):
        with pytest.raises(ValueError):
            AnthropicProvider(model=model, api_key=SECRET)


def test_missing_key_rejected_before_any_network(monkeypatch) -> None:
    monkeypatch.delenv(anthropic_provider.API_KEY_ENV_VAR, raising=False)
    captured = _fake_sdk(monkeypatch)
    with pytest.raises(ValueError) as excinfo:
        AnthropicProvider(model="claude-haiku-4-5")
    assert anthropic_provider.API_KEY_ENV_VAR in str(excinfo.value)
    assert captured["calls"] == 0


def test_env_var_supplies_key_when_not_passed(monkeypatch) -> None:
    monkeypatch.setenv(anthropic_provider.API_KEY_ENV_VAR, SECRET)
    provider = AnthropicProvider(model="claude-haiku-4-5")
    assert provider._key == SECRET


def test_key_absent_from_repr_and_public_attribute() -> None:
    provider = _provider()
    assert SECRET not in repr(provider)
    assert provider.api_key is None  # not retained on a public attribute


def test_construction_makes_no_network_call(monkeypatch) -> None:
    captured = _fake_sdk(monkeypatch)
    _provider()
    assert captured["calls"] == 0
    assert captured["client_kwargs"] is None  # client is built lazily


def test_missing_sdk_raises_actionable_error(monkeypatch) -> None:
    def _boom() -> None:
        raise MissingLLMDependencyError(
            f"AnthropicProvider requires the 'anthropic' package. {anthropic_provider.INSTALL_HINT}"
        )

    monkeypatch.setattr(anthropic_provider, "_load_sdk", _boom)
    with pytest.raises(MissingLLMDependencyError) as excinfo:
        _provider().generate(_request())
    assert "failurelab[anthropic]" in str(excinfo.value)


# --- request construction ----------------------------------------------------


def test_request_shape_and_bounds(monkeypatch) -> None:
    captured = _fake_sdk(monkeypatch)
    _provider().generate(_request())

    assert captured["calls"] == 1  # exactly one request
    assert captured["client_kwargs"] == {"api_key": SECRET, "max_retries": 0}
    assert captured["with_options"] == [{"timeout": 12.5}]

    kwargs = captured["kwargs"]
    assert kwargs["model"] == "claude-haiku-4-5"
    assert kwargs["max_tokens"] == 1024
    assert kwargs["system"] == "SYSTEM"
    assert kwargs["thinking"] == {"type": "disabled"}
    assert kwargs["output_config"]["format"]["schema"] == RESPONSE_SCHEMA
    assert kwargs["messages"][0]["role"] == "user"
    assert "failure_rate" in kwargs["messages"][0]["content"]


def test_sampling_parameters_never_sent(monkeypatch) -> None:
    """Current models reject temperature/top_p/top_k with a 400."""
    captured = _fake_sdk(monkeypatch)
    _provider().generate(_request())
    for banned in ("temperature", "top_p", "top_k"):
        assert banned not in captured["kwargs"]


def test_no_streaming_or_tools(monkeypatch) -> None:
    captured = _fake_sdk(monkeypatch)
    _provider().generate(_request())
    for absent in ("stream", "tools", "tool_choice"):
        assert absent not in captured["kwargs"]


def test_schema_shared_with_ollama_adapter() -> None:
    """Both adapters constrain output to the identical schema object."""
    from failurelab.llm import ollama

    assert ollama.RESPONSE_SCHEMA is RESPONSE_SCHEMA


# --- response mapping --------------------------------------------------------


def test_response_and_usage_mapping(monkeypatch) -> None:
    _fake_sdk(monkeypatch)
    response = _provider().generate(_request())
    assert response.text == json.dumps(VALID_INTERPRETATION)
    assert response.model == "claude-haiku-4-5-fake"
    assert response.token_usage == {"input_tokens": 321, "output_tokens": 65}


# --- error mapping -----------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_AuthenticationError(SECRET, 401), "rejected the API key"),
        (_PermissionDeniedError(SECRET, 403), "not permitted"),
        (_NotFoundError(SECRET, 404), "was not found"),
        (_RateLimitError(SECRET, 429), "rate limit"),
        (_APITimeoutError(SECRET), "timed out"),
        (_APIConnectionError(SECRET), "Could not connect"),
        (_APIStatusError(SECRET, 503), "HTTP status 503"),
    ],
)
def test_error_mapping_is_sanitized(monkeypatch, error: Exception, expected: str) -> None:
    _fake_sdk(monkeypatch, error=error)
    with pytest.raises(SanitizedProviderError) as excinfo:
        _provider().generate(_request())
    message = str(excinfo.value)
    assert expected in message
    assert SECRET not in message


def test_provider_error_secret_absent_from_traceback(monkeypatch) -> None:
    _fake_sdk(monkeypatch, error=_AuthenticationError(SECRET, 401))
    formatted = ""
    try:
        _provider().generate(_request())
    except SanitizedProviderError as error:
        formatted = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    assert formatted
    assert SECRET not in formatted


def test_refusal_is_reported(monkeypatch) -> None:
    _fake_sdk(monkeypatch, response=_Response("", stop_reason="refusal"))
    with pytest.raises(SanitizedProviderError) as excinfo:
        _provider().generate(_request())
    assert "declined" in str(excinfo.value)


def test_truncated_response_is_actionable(monkeypatch) -> None:
    _fake_sdk(monkeypatch, response=_Response("{}", stop_reason="max_tokens"))
    with pytest.raises(SanitizedProviderError) as excinfo:
        _provider().generate(_request())
    assert "max_output_tokens" in str(excinfo.value)


def test_empty_content_is_reported(monkeypatch) -> None:
    _fake_sdk(monkeypatch, response=_Response(""))
    with pytest.raises(SanitizedProviderError) as excinfo:
        _provider().generate(_request())
    assert "no text content" in str(excinfo.value)


# --- integration with interpret ---------------------------------------------


def test_interpret_end_to_end_with_fake_sdk(monkeypatch) -> None:
    captured = _fake_sdk(monkeypatch)
    interp = fl.interpret(_analysis_report(), provider=_provider())
    assert captured["calls"] == 1
    assert interp.summary == "ok"
    assert [o.statement for o in interp.observations] == ["grounded"]
    meta = interp.generation_metadata
    assert meta.provider == "anthropic"
    assert meta.model == "claude-haiku-4-5-fake"
    assert meta.token_usage == {"input_tokens": 321, "output_tokens": 65}


def test_interpret_passes_sanitized_error_through(monkeypatch) -> None:
    _fake_sdk(monkeypatch, error=_AuthenticationError(SECRET, 401))
    with pytest.raises(SanitizedProviderError) as excinfo:
        fl.interpret(_analysis_report(), provider=_provider())
    assert "rejected the API key" in str(excinfo.value)
    assert SECRET not in str(excinfo.value)


def test_key_absent_from_provenance(monkeypatch) -> None:
    _fake_sdk(monkeypatch)
    interp = fl.interpret(_analysis_report(), provider=_provider())
    assert SECRET not in json.dumps(interp.to_dict())
