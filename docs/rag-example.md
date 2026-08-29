# RAG example

A complete, runnable RAG application that emits FailureLab traces, lives in
[`examples/rag_pipeline/`](https://github.com/yellepeddibk/failurelab/tree/main/examples/rag_pipeline).

```text
documents -> chunking -> BM25 retrieval -> prompt -> generator
          -> answer + citations -> evaluation -> FailureLab traces
          -> analyze / compare -> optional interpret
```

It adds no dependencies. Retrieval is implemented with the standard library, and the
live generator speaks to Ollama over `urllib`.

## Run it

```bash
# Deterministic. No model required. Reproduces the committed datasets exactly.
python examples/rag_pipeline/run.py --output ./rag-out

# Live, against a local Ollama model you have pulled.
python examples/rag_pipeline/run.py --generator ollama --model gemma3 --output ./rag-out
```

Then analyze the result:

```bash
failurelab analyze examples/rag_pipeline/data/rag_v1.jsonl \
  --config examples/rag_pipeline/config.yaml --output ./reports

failurelab compare \
  examples/rag_pipeline/data/rag_v1.jsonl \
  examples/rag_pipeline/data/rag_v2.jsonl \
  --config examples/rag_pipeline/config.yaml --output ./reports/comparison
```

## The corpus and question set

Twenty-five short Markdown documents describing a fictional company's runbooks,
policies, postmortems, procedures, and reference material. They are written to
contain three near-duplicate service runbooks, because near-duplicates are where
lexical retrieval genuinely struggles.

Forty questions carry an **exhaustive** gold chunk set, in four categories:

| Category | Gold chunks | Correct behavior |
| --- | --- | --- |
| `single_source` | one | answer, citing it |
| `multi_source` | two or more | answer, citing all of them |
| `distractor` | one, with near-duplicates present | answer, citing the right one |
| `unanswerable` | none | abstain, citing nothing |

Gold sets being exhaustive is what lets the evaluator distinguish citing something
wrong from citing too little.

## What the evaluation measures

Every answered question is classified into exactly one outcome. Conditions are
checked in pipeline order, so a question whose evidence was never retrieved is
recorded as a retrieval failure even if generation also misbehaved.

**Answerable questions:**

| Condition | Outcome |
| --- | --- |
| the generator abstained | `unwarranted_refusal` |
| gold not all retrieved | `retrieval_miss` |
| answer text is blank | `empty_answer` |
| nothing cited | `grounding_failure` |
| cited something never retrieved | `invalid_citation` |
| cited outside the gold set | `wrong_source` |
| cited only part of the gold set | `incomplete_citation` |
| otherwise | success |

**Unanswerable questions:** abstaining with no citations succeeds, abstaining while
citing is `wrong_source`, and answering at all is `fabricated_answer`.

!!! warning "This is an evidence criterion, not a correctness criterion"
    Success means the pipeline retrieved the required evidence and cited exactly
    that evidence. A fluent but factually wrong answer that cites the right chunks
    is scored as a success. Measuring answer correctness would require a judge, and
    a judge is not deterministic.

## What FailureLab finds

Analyzing the two answerable runs together, on 64 traces:

- `failure_rate` around 0.27
- a **`retriever_version` failure slice** identifying `bm25-v1` as the worse variant
- root-cause hypotheses for every failed trace, separating retrieval failures from
  generation failures
- a replayable regression draft per failed trace

A slice on `retriever_version` only forms when both runs are analyzed together.
Analyzing either run alone gives every trace the same value, so there is nothing to
compare against.

!!! note "`failure_type` slices are close to tautological"
    Every `failure_type` slice reports a failure rate of 1.0, because a failure type
    only exists on a failed trace. They are useful for counting, not for discovery.
    `retriever_version` is the dimension that carries information here.

## Measured results

The corpus, chunking, and question set were frozen before either retriever was
evaluated, and these numbers are whatever the frozen benchmark produced.

| Retriever | recall@5 | failure rate |
| --- | ---: | ---: |
| `bm25-v1` (title indexed once) | 0.9375 | 0.28125 |
| `bm25-title-boosted` (title weighted 3x) | 0.9531 | 0.25000 |

Title boosting helped, but **not where it was designed to help**. The `distractor`
questions scored a perfect 1.000 under *both* retrievers: indexing the title once was
already enough to separate three near-identical runbooks, so the trap never sprang.
The entire gain came from `multi_source` questions, which went from 0.875 to 0.938.

Two retrieval failures survive both retrievers:

- **`q006`, "What is an escalation owner?"** The glossary chunk that *defines* the
  term is outranked by the many chunks that merely *use* it. A definitional query
  losing to usage-heavy documents is a classic lexical retrieval failure.
- **`q021`, "What happens if an escalation owner does not acknowledge an alert?"**
  The consequence lives in a later chunk than the one retrieval returns.

## Configuration matters more than it looks

`retrieval_k` in the analysis config **must match the `k` the pipeline retrieved
with**. FailureLab computes `retrieval_recall_at_k` by truncating `retrieved_sources`
to the configured `k`.

During development, the default of 3 was left in place against a pipeline retrieving
5. Both retrievers then scored an identical 0.90625 and the difference between them
was completely invisible, because it appears at ranks 4 and 5. `config.yaml` sets
`retrieval_k: 5`, and a test asserts it equals the pipeline's `k` so the mismatch
cannot return quietly.

## The abstention partition

Unanswerable questions live in their own dataset rather than mixed into the main one.
A correct refusal is a nonempty answer with zero citations, so mixing refusals in
would drag down citation metrics while the pipeline behaved perfectly.

That partition also demonstrates FailureLab's unavailable-metric contract on real
data. No question there has expected sources, so:

```json
{
  "name": "retrieval_recall_at_k",
  "value": null,
  "eligible_count": 0,
  "excluded_count": 8,
  "unavailable_reason": "no eligible traces"
}
```

The value is `null` with a real excluded count and a reason, never a fabricated
number over a denominator of 1.

## What the committed datasets are

`data/rag_v1.jsonl`, `data/rag_v2.jsonl`, and `data/rag_abstention.jsonl` are produced
by the scripted generator, and a test regenerates them and compares the bytes, so they
cannot drift from the pipeline.

Be precise about what is real in them:

- **Retrieval failures are genuine.** They come from real BM25 ranking over the real
  corpus.
- **Generation failures are authored.** A language model cannot be made to fail
  reproducibly on demand, and continuous integration cannot depend on one that tries.

Live runs against Ollama produce real generation behavior, and are not committed
because they are not reproducible.

## Live verification, and one unresolved hang

The deterministic path is fully reproducible. The live path was verified against a
local `gemma3` and is reported here exactly as measured.

**Abstention partition, 8 of 8 completed.** The model abstained correctly on seven
questions and produced one genuine, unseeded failure:

> `q034`, "Which cloud provider hosts the payments service?" was answered with "The
> payments service runs in the primary region", citing `runbook-payments#0`, instead
> of abstaining.

The corpus never names a cloud provider. The model latched onto adjacent context
about regions and produced a plausible non-answer. The pipeline classified it as
`fabricated_answer`. That is the failure the abstention partition exists to catch,
and it was found by a real model rather than authored.

**Answerable partition, 30 of 31 completed.** Per-question latency varied widely on
the same hardware, from 8.2 to 49.4 seconds, and the same question measured 13.0
seconds on one run and 43.8 seconds on another. Treat any timing here as indicative
only.

**`q006` hangs reproducibly.** "What is an escalation owner?" times out every time,
three attempts out of three. Its retrieved context is five chunks that all *mention*
the term while none *defines* it, because retrieval misses the glossary chunk. The
other retrieval miss, `q021`, completes normally in 16.5 seconds, so a retrieval miss
alone does not explain it.

Bounding generated output did **not** resolve it. The cause is not established, and
it is not claimed to be a defect in this example: the request is well formed, the
budget is bounded, and the generator times out with an actionable message rather than
hanging forever. If you hit it, `--timeout` and `--max-output-tokens` are available,
and the deterministic path remains the reproducible reference.

## Limitations

- Lexical retrieval only. No embeddings, no semantic search.
- The corpus is small and synthetic, so the absolute numbers mean nothing outside it.
- Success measures citation behavior, not answer quality.
- Nothing here establishes causation. A failure slice reports where failure is
  elevated, not why.
