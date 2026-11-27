#!/usr/bin/env bash
# scripts/wsl-setup.sh
# Run once inside Ubuntu on WSL2, immediately after the first login.
#
#   bash scripts/wsl-setup.sh
#
# Idempotent: safe to run again if something goes wrong halfway.

set -uo pipefail
FAIL=0

say() { printf '\n\033[1m%s\033[0m\n' "$1"; }
ok()  { printf '  \033[32mOK\033[0m    %s\n' "$1"; }
bad() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAIL=1; }
note(){ printf '  \033[33mNOTE\033[0m  %s\n' "$1"; }

say "1/5  apt update"
if sudo apt-get update -qq; then ok "package lists refreshed"; else bad "apt update failed — check DNS and network"; fi

say "2/5  install tooling"
if sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
     nftables iproute2 python3 python3-pip git curl ca-certificates jq less nano >/dev/null 2>&1
then ok "nftables, iproute2, python3, git, curl, jq"; else bad "package install failed"; fi

say "3/5  versions"
nft --version  >/dev/null 2>&1 && ok "$(nft --version)"       || bad "nft missing"
ip -V          >/dev/null 2>&1 && ok "$(ip -V)"               || bad "iproute2 missing"
python3 --version              >/dev/null 2>&1 && ok "$(python3 --version 2>&1)" || bad "python3 missing"
git --version  >/dev/null 2>&1 && ok "$(git --version)"       || bad "git missing"

say "4/5  IPv6 in the kernel"
if [[ -f /proc/sys/net/ipv6/conf/all/disable_ipv6 ]]; then
  v=$(cat /proc/sys/net/ipv6/conf/all/disable_ipv6)
  if [[ "$v" == "0" ]]; then ok "IPv6 enabled"
  else bad "IPv6 disabled (disable_ipv6=$v) — the whole project needs it"; fi
else
  bad "kernel has no IPv6 stack"
fi

say "5/5  network namespaces"
if sudo ip netns add _hf_probe 2>/dev/null; then
  sudo ip netns del _hf_probe 2>/dev/null
  ok "namespaces can be created (CAP_SYS_ADMIN present)"
else
  bad "cannot create network namespaces — run this script, not the individual commands"
fi

say "summary"
if [[ "$FAIL" -eq 0 ]]; then
  printf '  \033[32mREADY\033[0m  Now run:  sudo bash scripts/check-env.sh --live\n\n'
  exit 0
else
  printf '  \033[31mNOT READY\033[0m  Fix the FAIL lines above before continuing.\n\n'
  exit 1
fi
