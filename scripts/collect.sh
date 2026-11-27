#!/usr/bin/env bash
# scripts/collect.sh - run the generation matrix, resumably.
#
#   sudo bash scripts/collect.sh --conditions C1,C2 --repeats 3
#   sudo bash scripts/collect.sh --dry-run
#
# A cell is (scenario, condition, model, repeat). Its file name is built only
# from those four things, so rerunning the script after an interruption skips
# what already exists. Nothing is overwritten: to redo a cell, delete its row
# yourself, deliberately.
#
# Everything goes through generate/run_models.py; this script adds no
# behaviour, only looping.

set -uo pipefail

conditions="C1"
repeats=3
models="local:qwen2.5-coder:7b"
scenarios="./bench/scenarios/[0-9]*"
out="results"
dry=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --conditions) conditions="${2:-}"; shift 2 ;;
    --repeats)    repeats="${2:-}"; shift 2 ;;
    --models)     models="${2:-}"; shift 2 ;;
    --scenarios)  scenarios="${2:-}"; shift 2 ;;
    --out)        out="${2:-}"; shift 2 ;;
    --dry-run)    dry=1; shift ;;
    -h|--help)    sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)            echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$out" "$out/_logs"
planned=0
done_=0
failed=0

for scen in $scenarios; do
  [[ -d "$scen" ]] || continue
  sid="$(basename "$scen")"
  for cond in ${conditions//,/ }; do
    for spec in ${models//,/ }; do
      mid="$(printf '%s' "$spec" | sed 's/[^A-Za-z0-9._-]\+/-/g')"
      for rep in $(seq 1 "$repeats"); do
        row="$out/${sid}__${cond}__${mid}__r${rep}.json"
        planned=$((planned + 1))
        if [[ -f "$row" ]]; then
          done_=$((done_ + 1))
          [[ $dry -eq 1 ]] && echo "have  $row"
          continue
        fi
        if [[ $dry -eq 1 ]]; then
          echo "todo  python3 generate/run_models.py --scenario $scen --model $spec --condition $cond --repeat $rep --out $out"
          continue
        fi
        log="$out/_logs/${sid}__${cond}__${mid}__r${rep}.log"
        echo "==> $sid $cond $spec r$rep"
        python3 generate/run_models.py --scenario "$scen" --model "$spec" \
                --condition "$cond" --repeats "$rep" --out "$out" > "$log" 2>&1
        rc=$?
        if [[ $rc -eq 0 && -f "$row" ]]; then
          echo "    ok  $(grep -o 'ipv6=[a-z]*' "$log" | tail -1) $(grep -o 'parity=[a-z]*' "$log" | tail -1)"
        elif [[ $rc -eq 2 ]]; then
          echo "    HARNESS FAILURE (exit 2) - stopping. Last log lines:" >&2
          tail -5 "$log" >&2
          exit 2
        else
          echo "    no row (exit $rc) - see $log" >&2
          failed=$((failed + 1))
        fi
      done
    done
  done
done

echo
echo "cells planned: $planned   already present: $done_   failed: $failed"
if [[ $dry -eq 1 ]]; then
  echo "(dry run - nothing was called)"
fi
