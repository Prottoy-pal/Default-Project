# Ethics and Safety

This project deliberately has the smallest possible attack surface. Everything runs on one machine, inside an isolated virtual lab, against services we start ourselves.

---

## The four rules

### 1. Host-only networking — never bridged

The lab VM/WSL instance must **not** have a bridged adapter.

A bridged VM receives a real, globally routable IPv6 address from the ISP prefix. A generated configuration containing defect **D** (fail-open on IPv6) would then expose a live host to the public Internet for the duration of the experiment.

**Verify before every session:**

```bash
ip -6 addr show scope global
```

The only permitted addresses are:

- `fe80::/10` — link-local
- `fd00::/8` — unique-local

If you see `2000::/3`, the lab is exposed. Stop and fix the network mode.

### 2. Snapshot before every run

A generated ruleset can lock you out of the VM. Take a snapshot, or recreate the namespace, before each configuration is applied.

### 3. No third-party systems, ever

- No scanning of any host we do not own.
- No testing against real routers, ISPs, universities, or public services.
- No traffic capture beyond our own lab interfaces.
- No credentials, no personal data, no human subjects.

### 4. Vulnerable services are built by us, on purpose

The exploit demonstration uses a small service we write ourselves, designed to be reachable. We never point at a real application.

---

## What this project is not

| Not this | Why |
|---|---|
| A vulnerability disclosure | We test our own lab, not vendor products |
| An attack tool | The "attack" is a TCP connect from one namespace to another |
| Human-subjects research | No participants, no survey, no personal data |
| A production hardening guide | We measure behaviour; we do not certify configurations |

---

## If we later test a real vendor's documentation

RQ3 retrieves from official nftables and CIS documentation. If a vendor hardening guide is found to be IPv6-incomplete, we:

1. Do not name the vendor in the paper until disclosure is complete.
2. Report the finding privately first.
3. Publish only the mechanism and the aggregate result.

---

## Data handling

- Generated configurations are synthetic text. No secrets.
- Model outputs are published verbatim, including failures.
- No IP addresses belonging to real people or organisations appear in the dataset. Lab addresses use RFC 5737 (`10.0.0.0/8`-style) and RFC 3849 (`2001:db8::/32`) documentation ranges.

---

## Checklist before every experiment session

```
[ ] Lab adapter is host-only (no global IPv6 address)
[ ] Snapshot taken / namespaces recreated
[ ] Only 10.x and 2001:db8::/32 addresses in use
[ ] No real hostnames or public IPs in generated configs
[ ] Results committed with the model version recorded
```
