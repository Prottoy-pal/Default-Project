# results/

Raw experiment output. Git-ignored by design: every row is a JSON file that
is **regenerable** from the committed scenario, prompt and model configuration,
because the runner uses a deterministic seed and records the model digest.

## Regenerating

Inside Ubuntu (WSL2):

```bash
sudo bash scripts/collect.sh --conditions C1,C2 --repeats 1 \
     --models local:qwen2.5-coder:7b --out results
python3 scripts/analyze.py results/
```

A cell is addressed by `{scenario}__{condition}__{model}__r{repeat}`, and the
runner refuses to overwrite an existing row unless `--force` is given, so a
batch can be interrupted and resumed without duplicating work.

## What is in a row

One row per cell, carrying the prompt and its hash, the raw model output, the
blindly-extracted ruleset, the model digest and sampling parameters, the apply
result (including the parse error, when there is one), every probe's observed
vs expected outcome per family, the defect classification, and the host kernel.

The aggregate numbers are reported in `docs/pilot-report.md`, not kept only
here.
