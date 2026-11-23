#!/usr/bin/env bash
# Half a Firewall — environment check
# Verifies that this machine can run the benchmark.
# Usage: bash scripts/check-env.sh
#
# Exit code 0 = ready. Anything else = fix the lab before running experiments.

set -uo pipefail
FAIL=0

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAIL=1; }
warn() { printf '  \033[33mWARN\033[0m  %s\n' "$1"; }
head_() { printf '\n\033[1m%s\033[0m\n' "$1"; }

head_ "Half a Firewall :: environment check"

# ---------------------------------------------------------------- platform
head_ "Platform"
if [[ "$(uname -s)" == "Linux" ]]; then
  pass "Linux kernel $(uname -r)"
  if grep -qi microsoft /proc/version 2>/dev/null; then
    pass "WSL2 detected"
  fi
else
  fail "Not Linux. Use WSL2 (wsl --install -d Ubuntu) or a Linux VM."
fi

# ---------------------------------------------------------------- tooling
head_ "Required tools"
for bin in nft ip python3 git; do
  if command -v "$bin" >/dev/null 2>&1; then
    pass "$bin -> $(command -v "$bin")"
  else
    fail "$bin not found"
  fi
done

command -v unshare >/dev/null 2>&1 && pass "unshare available" || warn "unshare missing (needed for namespace isolation)"

# ---------------------------------------------------------------- privileges
head_ "Privileges"
if [[ "$(id -u)" -eq 0 ]]; then
  pass "running as root"
elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
  pass "passwordless sudo available"
else
  warn "not root; netns setup will prompt for sudo"
fi

# ---------------------------------------------------------------- IPv6
head_ "IPv6"
if [[ -f /proc/sys/net/ipv6/conf/all/disable_ipv6 ]]; then
  if [[ "$(cat /proc/sys/net/ipv6/conf/all/disable_ipv6)" == "0" ]]; then
    pass "IPv6 enabled in kernel"
  else
    fail "IPv6 disabled at kernel level (net.ipv6.conf.all.disable_ipv6=1)"
  fi
else
  fail "no /proc/sys/net/ipv6 — kernel built without IPv6"
fi

# ---------------------------------------------------------------- nftables
head_ "nftables"
if command -v nft >/dev/null 2>&1; then
  ver=$(nft --version 2>/dev/null | head -1)
  pass "$ver"
  if nft list tables >/dev/null 2>&1; then
    pass "can read the ruleset"
  else
    warn "cannot read ruleset without root (expected)"
  fi
  if nft describe inet >/dev/null 2>&1; then
    pass "inet table family supported"
  else
    warn "could not verify inet family"
  fi
fi

# ---------------------------------------------------------------- live test
head_ "Live isolation test (optional)"
if [[ "${1:-}" == "--live" ]]; then
  echo "  building the standard lab: 3 namespaces, 2 veth pairs ..."
  echo "  (addresses mirror bench/topology.yaml)"

  for ns in fw cli_admin cli_wan; do sudo ip netns del "$ns" 2>/dev/null; done
  if sudo ip netns add fw && sudo ip netns add cli_admin && sudo ip netns add cli_wan; then
    pass "namespaces created"

    # --- links: unique names in the root namespace, renamed after moving ---
    sudo ip link add veth_admin type veth peer name veth_admin_p
    sudo ip link add veth_wan   type veth peer name veth_wan_p
    sudo ip link set veth_admin   netns fw
    sudo ip link set veth_admin_p netns cli_admin
    sudo ip link set veth_wan     netns fw
    sudo ip link set veth_wan_p   netns cli_wan
    sudo ip -n fw        link set veth_admin   name eth_admin
    sudo ip -n fw        link set veth_wan     name eth_wan
    sudo ip -n cli_admin link set veth_admin_p name eth0
    sudo ip -n cli_wan   link set veth_wan_p   name eth0

    # --- addresses: documentation ranges only ---
    sudo ip -n fw addr add 10.20.0.1/24        dev eth_admin
    sudo ip -n fw addr add 198.51.100.1/24     dev eth_wan
    sudo ip -n fw addr add 2001:db8:20::1/64   dev eth_admin nodad
    sudo ip -n fw addr add 2001:db8:100::1/64  dev eth_wan   nodad
    sudo ip -n cli_admin addr add 10.20.0.10/24      dev eth0
    sudo ip -n cli_admin addr add 2001:db8:20::10/64 dev eth0 nodad
    sudo ip -n cli_wan   addr add 198.51.100.10/24     dev eth0
    sudo ip -n cli_wan   addr add 2001:db8:100::10/64  dev eth0 nodad

    for ns in fw cli_admin cli_wan; do
      sudo ip -n "$ns" link set lo up
      sudo ip -n "$ns" link set eth0 up 2>/dev/null
      sudo ip netns exec "$ns" sysctl -qw net.ipv6.conf.all.accept_ra=0 2>/dev/null
    done
    sudo ip -n fw link set eth_admin up
    sudo ip -n fw link set eth_wan up

    # --- the two assertions that matter ---
    if sudo ip netns exec cli_admin ping -c1 -W2 10.20.0.1 >/dev/null 2>&1; then
      pass "IPv4 across a veth pair"
    else
      fail "IPv4 unreachable"
    fi
    if sudo ip netns exec cli_admin ping -6 -c1 -W3 2001:db8:20::1 >/dev/null 2>&1; then
      pass "IPv6 across a veth pair"
    else
      fail "IPv6 unreachable — check that the kernel has IPv6 and that DAD settled"
    fi

    for ns in fw cli_admin cli_wan; do sudo ip netns del "$ns"; done
    pass "cleaned up"
  else
    fail "could not create namespaces (need root)"
  fi
else
  warn "skipped — rerun as: sudo bash scripts/check-env.sh --live"
fi

# ---------------------------------------------------------------- verdict
head_ "Verdict"
if [[ "$FAIL" -eq 0 ]]; then
  printf '  \033[32mREADY\033[0m — lab looks good.\n'
  exit 0
else
  printf '  \033[31mNOT READY\033[0m — fix the FAIL lines above.\n'
  exit 1
fi
