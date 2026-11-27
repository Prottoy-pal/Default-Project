"""generate/run_models.py - prompt a model, extract blindly, execute, record one row.

    sudo python3 generate/run_models.py \
        --scenario bench/scenarios/01-ssh-bastion \
        --model local:qwen2.5-coder:7b \
        --condition C1 --repeats 3 \
        --out results/

Why sudo: the scoring step builds network namespaces and loads nftables. The
model call itself needs no privilege; it talks to Ollama on localhost.

Contract, from generate/README.md:
  * the prompt is the only thing the model sees;
  * extraction is blind - first fenced block, else the whole message, never
    repaired by hand;
  * a refusal is data, not an error;
  * one JSON row per (scenario, model, condition, repeat), and the row carries
    the raw output next to the execution verdict.

Exit codes
    0  every requested cell produced a row (the model may still have failed)
    2  the runner itself could not proceed - bad scenario, no model, no lab
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROMPTS = Path(__file__).resolve().parent / "prompts"
OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
FENCE = re.compile(r"```[A-Za-z0-9_+-]*[ \t]*\n(.*?)```", re.S)
CONDITIONS = ("C1", "C2", "C3", "C4")


def die(msg):
    print(msg, file=sys.stderr)
    raise SystemExit(2)


# --------------------------------------------------------------- prompts ----
def read_prompt_file(name):
    path = PROMPTS / name
    if not path.is_file():
        die(f"missing prompt fragment: {path}")
    return path.read_text(encoding="utf-8").strip()


def compose(condition, policy_prompt, retrieval=None, previous=None, failures=None):
    """Build the exact text the model receives. Nothing else is ever sent."""
    base = policy_prompt.strip()

    if condition == "C1":
        return base + "\n"

    if condition == "C2":
        # The original plan appended "this server has a public IPv4 and a
        # public IPv6 address". Every scenario prompt already states that,
        # so the sentence was a no-op and C1 == C2 by construction. What C2
        # actually needs to isolate is the *instruction to enforce on both
        # families*, as opposed to the bare fact that both exist.
        return base + "\n\n" + read_prompt_file("c2-both-families.md") + "\n"

    if condition == "C3":
        if not retrieval:
            die("C3 needs retrieved passages; build generate/retrieval/ first")
        block = read_prompt_file("c3-header.md")
        for i, passage in enumerate(retrieval, 1):
            block += f"\n\n[passage {i} - {passage['source']}]\n{passage['text'].strip()}"
        return base + "\n\n" + block + "\n"

    if condition == "C4":
        if previous is None:
            return base + "\n"
        text = base + "\n\n" + read_prompt_file("c4-repair.md")
        text += "\n\nYour previous ruleset:\n\n```nft\n" + previous.strip() + "\n```\n"
        text += "\nWhen executed in the lab it failed these checks:\n\n"
        for line in failures or []:
            text += f"  - {line}\n"
        text += "\nReturn a corrected ruleset only, in a single fenced code block. "
        text += "Do not explain.\n"
        return text

    die(f"unknown condition {condition!r}")


def extract(text):
    """First fenced block, else the whole message. Never repaired."""
    m = FENCE.search(text)
    body = m.group(1) if m else text
    body = body.strip()
    if body and not body.endswith("\n"):
        body += "\n"
    return body


# ---------------------------------------------------------------- ollama ----
def http_json(url, payload=None, timeout=900):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def ollama_tags():
    try:
        return http_json(OLLAMA + "/api/tags", timeout=10).get("models", [])
    except (urllib.error.URLError, OSError) as exc:
        die(f"cannot reach Ollama at {OLLAMA}: {exc}\n"
            f"  start it with: sudo systemctl start ollama")


def model_digest(tag):
    for m in ollama_tags():
        name = m.get("name", "")
        if name == tag or name == tag + ":latest" or name.split(":")[0] == tag:
            return {
                "digest": m.get("digest", ""),
                "parameter_size": m.get("details", {}).get("parameter_size", ""),
                "quantization": m.get("details", {}).get("quantization_level", ""),
                "size_bytes": m.get("size", 0),
            }
    die(f"model {tag!r} is not installed. Installed: "
        + ", ".join(m.get("name", "?") for m in ollama_tags()))


def ollama_generate(tag, prompt, seed):
    payload = {
        "model": tag,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "top_p": 1.0,
            "seed": seed,
            "num_predict": 1200,
            "num_ctx": 4096,
        },
    }
    started = time.monotonic()
    d = http_json(OLLAMA + "/api/generate", payload)
    wall_ms = int((time.monotonic() - started) * 1000)
    return {
        "text": d.get("response", ""),
        "wall_ms": wall_ms,
        "total_duration_ms": int(d.get("total_duration", 0) / 1e6),
        "load_duration_ms": int(d.get("load_duration", 0) / 1e6),
        "prompt_eval_count": d.get("prompt_eval_count"),
        "eval_count": d.get("eval_count"),
        "done_reason": d.get("done_reason"),
    }


# ---------------------------------------------------------------- scoring ---
def run_score(scenario, config, condition, model_id, repeat, out):
    cmd = [
        sys.executable, str(REPO / "harness" / "score.py"),
        "--scenario", str(scenario),
        "--config", str(config),
        "--condition", condition,
        "--model", model_id,
        "--repeat", str(repeat),
        "--out", str(out),
        "--reset",
    ]
    r = subprocess.run(cmd)
    if r.returncode == 2:
        die("scoring reported a harness failure (exit 2); no row written")
    if not out.is_file():
        die(f"score.py exited {r.returncode} without writing {out}")
    return json.loads(out.read_text(encoding="utf-8"))


def summarise_probes(row):
    fails = [p for p in row["probes"] if p["verdict"] != "pass"]
    return {
        "verdicts": row["verdicts"],
        "defects": row["defects"],
        "passed": row["verdicts"]["passed"],
        "total": row["verdicts"]["total"],
        "failing": [
            {
                "id": p["id"],
                "proto": p["proto"],
                "port": p["port"],
                "family": p["family"],
                "expected": p["expected"],
                "observed": p["observed"],
            }
            for p in fails
        ],
    }


def failure_lines(failing):
    lines = []
    for f in failing:
        target = f"{f['proto']}" + (f":{f['port']}" if f["port"] else "")
        lines.append(f"{f['id']} ({target}, {f['family']}): "
                     f"required {f['expected']}, observed {f['observed']}")
    return lines


# ------------------------------------------------------------------- main ---
def main():
    ap = argparse.ArgumentParser(description="prompt -> extract -> execute -> row")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--model", required=True,
                    help="local:<ollama-tag>, e.g. local:qwen2.5-coder:7b")
    ap.add_argument("--condition", default="C1", choices=CONDITIONS)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--out", default="results")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-rounds", type=int, default=2,
                    help="C4 only: total generations, including the first")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the prompt that would be sent, call nothing")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing row with the same run_id")
    args = ap.parse_args()

    scenario = Path(args.scenario).resolve()
    if not (scenario / "policy.yaml").is_file():
        die(f"not a scenario directory (no policy.yaml): {scenario}")

    if not args.model.startswith("local:"):
        die("only local:<ollama-tag> is implemented; hosted providers are a "
            "separate change with their own provenance fields")
    tag = args.model.split(":", 1)[1]

    import yaml
    policy = yaml.safe_load((scenario / "policy.yaml").read_text(encoding="utf-8"))
    base_prompt = policy["prompt"]

    if args.dry_run:
        text = compose(args.condition, base_prompt)
        print(f"--- {policy['id']} {args.condition} "
              f"({len(text)} chars, sha256 {hashlib.sha256(text.encode()).hexdigest()[:16]}) ---")
        print(text)
        if args.condition == "C4":
            print("--- C4 also sends the previous ruleset and the failing "
                  "probes; not available before a first generation ---")
        return 0

    if os.geteuid() != 0:
        die("run with sudo: the scoring step needs namespaces and nftables")

    info = model_digest(tag)
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "_work"
    work.mkdir(exist_ok=True)
    model_id = re.sub(r"[^A-Za-z0-9._-]+", "-", args.model).strip("-")

    rows = []
    for repeat in range(1, args.repeats + 1):
        print(f"\n=== {policy['id']} · {args.model} · {args.condition} "
              f"· repeat {repeat}/{args.repeats} ===", flush=True)

        retrieval = None
        if args.condition == "C3":
            from retrieval import retrieve  # local module, built with the corpus
            retrieval = retrieve(base_prompt)

        previous = None
        failures = None
        rounds = []
        prompt = compose(args.condition, base_prompt, retrieval=retrieval)
        max_rounds = args.max_rounds if args.condition == "C4" else 1

        for rnd in range(1, max_rounds + 1):
            if args.condition == "C4" and rnd > 1:
                prompt = compose("C4", base_prompt, previous=previous, failures=failures)

            print(f"  round {rnd}: calling {tag} ...", end="", flush=True)
            call = ollama_generate(tag, prompt, args.seed + repeat * 100 + rnd)
            ruleset = extract(call["text"])
            print(f" {call['wall_ms']} ms, {len(ruleset)} chars of ruleset")

            cfg = work / f"{policy['id']}__{model_id}__{args.condition}__r{repeat}__g{rnd}.nft"
            cfg.write_text(ruleset, encoding="utf-8")

            row_path = out_dir / f".row__{policy['id']}__{model_id}__{args.condition}__r{repeat}__g{rnd}.json"
            row = run_score(scenario, cfg, args.condition, model_id, repeat, row_path)
            summary = summarise_probes(row)

            rounds.append({
                "round": rnd,
                "prompt": prompt,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "raw_output": call["text"],
                "extracted_ruleset": ruleset,
                "config_path": str(cfg.relative_to(REPO)) if cfg.is_relative_to(REPO) else str(cfg),
                "apply": row["apply"],
                "verdicts": summary["verdicts"],
                "defects": summary["defects"],
                "failing": summary["failing"],
                "model_call": {
                    "wall_ms": call["wall_ms"],
                    "total_duration_ms": call["total_duration_ms"],
                    "load_duration_ms": call["load_duration_ms"],
                    "prompt_eval_count": call["prompt_eval_count"],
                    "eval_count": call["eval_count"],
                    "done_reason": call["done_reason"],
                },
            })
            row_path.unlink(missing_ok=True)

            print(f"    ipv4={summary['verdicts']['ipv4']} "
                  f"ipv6={summary['verdicts']['ipv6']} "
                  f"parity={summary['verdicts']['parity']} "
                  f"defects={summary['defects'] or 'none'} "
                  f"({summary['passed']}/{summary['total']})")

            previous = ruleset
            failures = failure_lines(summary["failing"])
            if args.condition != "C4" or summary["verdicts"]["parity"] == "pass":
                break

        last = rounds[-1]
        final = row  # last scoring row, complete
        # Deterministic identity: a cell is addressed by what it is, not by
        # when it ran. That makes a batch resumable and a row citable.
        final["run_id"] = f"{policy['id']}__{args.condition}__{model_id}__r{repeat}"
        final["scenario"] = policy["id"]
        final["family"] = policy.get("family")
        final["variant"] = policy.get("variant")
        final["condition"] = args.condition
        final["repeat"] = repeat
        final["model"] = {
            "provider": "ollama",
            "name": tag,
            "tag": tag,
            "temperature": 0.0,
            "top_p": 1.0,
            "seed": args.seed,
            "spec": args.model,
            **info,
        }
        final["generation"] = {
            "prompt": rounds[0]["prompt"],
            "prompt_sha256": rounds[0]["prompt_sha256"],
            "raw_output": last["raw_output"],
            "extracted_ruleset": last["extracted_ruleset"],
            "extraction": ("first fenced block" if FENCE.search(last["raw_output"])
                           else "whole message"),
            "ollama": {"endpoint": OLLAMA, "version": ollama_version()},
            "retrieval": retrieval,
            "rounds": rounds,
        }

        out_file = out_dir / f"{final['run_id']}.json"
        if out_file.exists() and not args.force:
            die(f"{out_file} exists; the dataset is append-only. Use --force to "
                f"overwrite deliberately, or change --seed/--repeat")
        out_file.write_text(json.dumps(final, indent=2), encoding="utf-8")
        print(f"  row -> {out_file}")
        rows.append(out_file)

    print(f"\nwrote {len(rows)} row(s) to {out_dir}")
    return 0


def ollama_version():
    try:
        return http_json(OLLAMA + "/api/version", timeout=10).get("version", "")
    except (urllib.error.URLError, OSError):
        return ""


if __name__ == "__main__":
    sys.exit(main())
