# Privacy

FailureLab is local-first and excludes raw query/context content from reports by default.

## Third-party transmission (optional interpretation layer)

The core is offline and transmits nothing. The optional interpretation layer
(`failurelab.interpret`) is the only path that can send data to a third party,
and only when you explicitly construct a provider and call it. A model API key
present in your environment activates nothing on its own, and FailureLab does not
discover or load `.env` files.

By default (`include_content=False`, `include_trace_ids=False`), a request
contains only structured deterministic evidence: metric and slice descriptors,
root-cause hypothesis labels, and data-quality counts. It does not include raw
prompts, answers, retrieved context, tool arguments, regression inputs, or trace
IDs. Trace-scoped findings are referenced by local aliases whose mapping stays on
your machine and is excluded from `InterpretationReport.to_dict()` unless you ask
for it. Provenance stores prompt and response hashes, not raw text, and never
stores API keys.

Structured metadata is transmitted by default: metric names and values, slice
field labels and their values (for example `model=gpt-x`), hypothesis labels, and
data-quality counts. These are descriptors rather than raw content, but they can
carry user-defined metadata, so review them if your field values are sensitive.
