# generate/

Everything on the input side of the experiment: the prompts, the model calls,
and the extraction of a ruleset from whatever the model says.

```
prompts/          c1-plain.md · c2-dual-stack.md · c3-rag.md · c4-repair.md
run_models.py     call → extract → hand off to harness/run.sh → one JSON row
retrieval/        the corpus for C3, plus the log of what was retrieved per call
models.yaml       exact model identifiers, providers, sampling parameters
```

**Status:** implemented 28 November 2026. C1, C2 and C4 run end to end. C3 is
wired to the retriever but refuses to run until `retrieval/corpus/` has the
documentation passages in it — an empty corpus cannot support a C3 claim.

---

## Conditions

| Code | What the model receives | What this isolates |
|---|---|---|
| **C1** | The scenario prompt, unchanged | Baseline knowledge |
| **C2** | C1 + *"The ruleset must enforce this policy for both IPv4 and IPv6 traffic."* | Whether the model needed to be told to apply the policy to both families |
| **C3** | C1 + retrieved passages from the nftables wiki, `man nft`, RFC 9099 | Whether documentation closes the gap |
| **C4** | C1, then the failing probes, then one retry (max 2 rounds) | Whether feedback closes the gap |

C1 versus C2 is the load-bearing comparison. If C1 ≈ C2, an explicit dual-stack
instruction does not help, and the finding is about capability rather than
prompting. If C1 < C2, the failure is a prompting artefact — and that is the
more actionable result, because it names the one sentence an operator should
add.

**Why C2 changed.** The original design appended *"this server has a public IPv4
address and a public IPv6 address"*. Every scenario prompt already says exactly
that, and the authoring rules require both families' prefixes to be stated
whenever a source is scoped. The sentence would have been a no-op, and the
headline C1-vs-C2 comparison a tautology. C2 now carries the *instruction* to
enforce on both families, which is the intervention worth measuring. The change
was made before the first recorded row; no data was discarded.

C3 and C4 exist to answer RQ3, not to improve the headline number. Report all
four. A paper that only reports the condition that worked is not a measurement.

---

## Rules that keep the comparison honest

1. **The prompts are frozen before the first recorded run.** Any wording change
   starts a new dataset with a new `prompt_sha256`. No tuning between runs.
2. **`temperature = 0.0`, `top_p` recorded.** Three repeats exist to expose
   residual nondeterminism, not to be averaged into one nicer number.
3. **The model never sees `expected.yaml`, `expert.nft`, or any other
   scenario's files.** The prompt file is the only input.
4. **Retrieved passages are logged for every C3 call,** with the query that
   produced them. A RAG result whose retrieval cannot be inspected is not a
   result.
5. **Extraction is blind.** Pull the first fenced code block; if there is none,
   take the whole message. Never repair syntax by hand, never add a missing
   `flush ruleset`, never reorder rules. What the model produced is what gets
   applied.
6. **A refusal is data.** Record it with `apply.loaded = false` and the reason.

---

## Model selection

Three models minimum, at least one local and one hosted, on a **$0** budget:

| Slot | Candidate | Why |
|---|---|---|
| Small local | a 7–8B instruct model via Ollama | Free, reproducible, offline |
| Mid hosted | a current frontier model on a free tier | Establishes the ceiling |
| Contrast | one model from a different family or scale | Separates capability from behaviour |

Record the exact tag, quantisation, provider, date, and price-per-call if not
free. A model named only as "GPT" or "Llama" is not a result.

Everything runs through a plain Python + `requests`/`openai`-compatible client.
No agent framework, no orchestration layer — the pipeline has to be auditable
by a reader who has never seen the code.

---

## What one row costs to reproduce

```bash
python3 generate/run_models.py \
  --scenario bench/scenarios/01-ssh-bastion \
  --model local:qwen2.5-coder:7b \
  --condition C1 --repeats 3 \
  --out results/
```

That command is the whole contract. If it needs a second command, a config
file, or a manual step, it will not be reproduced by anyone, including you in
March.

---

## Dataset shape

`results/` holds raw JSON and is git-ignored; the released dataset is a
compressed archive published to Zenodo at the end of Sprint 1 and again at the
end of the project. Every released row carries the fields in
[harness/README.md](../harness/README.md#output), plus `prompt_sha256` and the
retrieval log for C3.
