# Interpretation (optional, opt-in)

FailureLab's core analysis is deterministic and offline. The optional
interpretation layer can turn a deterministic `AnalysisReport` into a
natural-language `InterpretationReport` using a language model you choose. It is
strictly opt-in: nothing runs a model unless you construct a provider and call
`interpret`.

## Guarantees

- The deterministic core never calls a model and needs no key. A key present in
  your environment activates nothing on its own.
- Exactly one model call per `interpret()`. No agent loop, no follow-up or
  repair calls, no automatic retries.
- Generated interpretation is a separate object; it never overwrites
  deterministic findings.
- Every generated claim is grounded. Observations must reference supplied
  evidence or they are dropped, and the summary must reference supplied evidence
  or the whole response is rejected. Malformed responses raise rather than
  triggering another paid call.
- Bounds are validated before the provider is contacted, so an invalid or
  oversized request never reaches it.
- The alias map is excluded from `to_dict()` by default, so serializing a report
  cannot leak original trace IDs. Pass `include_aliases=True` to include it
  deliberately, or use `resolve_reference()` for local resolution.
- By default only structured evidence is sent: metric and slice descriptors,
  hypothesis labels, and data-quality counts. Raw prompts, answers, retrieved
  context, tool arguments, regression inputs, and trace IDs are not sent unless
  you explicitly opt in.
- Trace-scoped findings are referenced by local aliases (`slice-001`,
  `hypothesis-001`); the alias-to-original mapping stays on your machine.
- Provenance records prompt and response hashes, model, template version,
  parameters, and token usage. Raw prompt and response text are not stored.

## Usage

```python
import failurelab as fl
from failurelab.llm import FakeProvider

report = fl.analyze("traces.jsonl")

# FakeProvider is deterministic and offline; use it for tests and demos.
interpretation = fl.interpret(report, provider=FakeProvider())

print(interpretation.summary)
for observation in interpretation.observations:
    print(observation.statement, [(r.kind, r.id) for r in observation.evidence])
print(interpretation.generation_metadata.to_dict())
```

## Providers

The provider protocol is vendor-neutral:

```python
class InterpretationProvider(Protocol):
    name: str
    def generate(self, request: InterpretationRequest) -> ProviderResponse: ...
```

You bring your own provider and model. FailureLab never owns, proxies, or pays
for model usage, and it does not read or load `.env` files on your behalf.

### Ollama (local or self-hosted, no API key)

`OllamaProvider` targets a **local or self-hosted** Ollama server and relies on
its structured-output support. Ollama Cloud is not supported. It uses only the
Python standard library, so it adds no dependency and needs no extra. The Ollama
runtime and the model are separate prerequisites that you install yourself:

```bash
python -m pip install failurelab
# Install Ollama separately from https://ollama.com
ollama pull <chosen-model>
```

`pip install failurelab` never installs Ollama and never downloads a model.

```python
import failurelab as fl
from failurelab.llm import OllamaProvider

provider = OllamaProvider(model="gemma3", host="http://localhost:11434")
interpretation = fl.interpret(report, provider=provider, timeout=300.0)
```

Note the explicit `timeout`. Local inference on CPU can take several minutes for
a single request, which exceeds the provider-neutral 30-second default. Raise the
timeout for CPU-only machines, and lower it when running on a GPU or with a
smaller and faster model. The default is deliberately conservative and unchanged.

Behavior worth knowing:

- The model must be named explicitly and pulled beforehand. The adapter never
  selects, downloads, or pulls a model for you.
- Constructing the provider performs no network call. One `interpret` call makes
  exactly one non-streaming `POST /api/chat` request, with `temperature=0` and a
  full JSON schema for structured output.
- No environment variable is read (including `OLLAMA_API_KEY`), and there are no
  retries, repair calls, or preflight requests.
- Errors are actionable but sanitized, naming only the host, model, and HTTP
  status. A missing model suggests `ollama pull <model>`.
- Setting `host` to anything other than localhost transmits the structured
  evidence to that machine or service. Raw content and trace IDs remain excluded
  unless you opt in through `failurelab.interpret`.

## Cost and privacy controls

- `include_content=False` (default): no raw content leaves your machine.
- `include_trace_ids=False` (default): trace IDs are pseudonymized.
- `max_output_tokens`, `max_evidence_items`, `max_evidence_bytes`, and `timeout`
  bound each call. All are validated before the provider is contacted.

Structured metadata is still transmitted by default: metric names and values,
slice field labels and their values (for example `model=gpt-x`), hypothesis
labels, and data-quality counts. These are descriptors rather than raw prompts,
answers, retrieved context, or tool arguments, but they can contain
user-defined metadata, so review them if your field values are sensitive.
