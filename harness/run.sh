#!/usr/bin/env bash
# harness/run.sh — the only entry point anyone else needs.
#
#   sudo bash harness/run.sh bench/scenarios/01-ssh-bastion \
#        --config bench/scenarios/01-ssh-bastion/expert.nft \
#        --out results/expert-01.json
#
# Exit codes: 0 all probes matched, 1 a probe disagreed, 2 harness failure.

set -uo pipefail
export PYTHONDONTWRITEBYTECODE=1

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

scenario=""
config=""
out=""
condition="expert"
repeat="1"
model="expert-config"
reset=0
keep=0
topology=""

usage() {
  sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)    config="${2:-}"; shift 2 ;;
    --out)       out="${2:-}"; shift 2 ;;
    --condition) condition="${2:-}"; shift 2 ;;
    --repeat)    repeat="${2:-}"; shift 2 ;;
    --model)     model="${2:-}"; shift 2 ;;
    --topology)  topology="${2:-}"; shift 2 ;;
    --reset)     reset=1; shift ;;
    --keep)      keep=1; shift ;;
    -h|--help)   usage ;;
    -*)          echo "unknown flag: $1" >&2; usage ;;
    *)           scenario="$1"; shift ;;
  esac
done

[[ -n "$scenario" ]] || usage
[[ -d "$scenario" ]] || { echo "no such scenario: $scenario" >&2; exit 2; }

# Default: the scenario's own expert configuration. That is the gate.
if [[ -z "$config" ]]; then
  config="$scenario/expert.nft"
fi
[[ -f "$config" ]] || { echo "no such config: $config" >&2; exit 2; }

args=(--scenario "$scenario" --config "$config"
      --condition "$condition" --repeat "$repeat" --model "$model")
[[ -n "$out" ]] && args+=(--out "$out")
[[ -n "$topology" ]] && args+=(--topology "$topology")
[[ $reset -eq 1 ]] && args+=(--reset)
[[ $keep  -eq 1 ]] && args+=(--keep)

exec python3 "$here/score.py" "${args[@]}"
