# Setting up the lab on Windows 11 (WSL2 + Ubuntu)

**Goal:** a Linux environment on this laptop where `nft` can build real firewall
rules and `ip netns` can create isolated networks with both IPv4 and IPv6.

No virtual machine software, no GPU, no cloud account, no money.

---

## What this machine already has

Checked on 28 November 2026:

| Item | Value | Verdict |
|---|---|---|
| Windows | 11 Pro, build 26300, 64-bit | fine |
| CPU | i7-13620H, 10 cores / 16 threads | fine |
| RAM | 15.7 GB | fine — enough for a 7–8B model later |
| Disk free | 291 GB on E: | fine |
| Virtualisation | hypervisor already running (Memory Integrity) | fine |
| WSL package | **3.0.5**, kernel 6.18.58.1 | done |
| `VirtualMachinePlatform` | **enabled** | done |
| Distribution | **Ubuntu 26.04.1 LTS, version 2**, at `E:\WSL\Ubuntu` | done |
| Account | `prottoy`, passwordless `sudo`, systemd on | done |
| Gate A | **passed 28 November 2026** | done |

Everything below is written as a first-time setup, and annotated with what this
machine actually did. On a rebuild you can start at step 3.

---

## Step 1 — Enable the Windows features (done)

```powershell
# elevated PowerShell
wsl --install -d Ubuntu --no-launch
```

This enabled `VirtualMachinePlatform`, downloaded the WSL 3.0.5 package, and
told Windows it needs a restart. The log is at
`%LOCALAPPDATA%\Temp\opencode\wsl-install.log`.

## Step 2 — Reboot (required)

Feature changes do not take effect until Windows restarts. Before the reboot,
`wsl --status` will still say *"virtualization is not enabled"* — that message
is about the pending reboot, not about your BIOS.

**Save your work and restart now.**

## Step 3 — Install and register Ubuntu

From PowerShell (normal, not elevated):

```powershell
wsl --install -d Ubuntu --location 'E:\WSL\Ubuntu' --no-launch
```

- `--location` puts the distribution's disk (`ext4.vhdx`) on E: instead of
  burying it in `%LOCALAPPDATA%`. On this machine that is 291 GB free rather
  than 125 GB.
- `--no-launch` downloads and registers the distribution without opening its
  first-run prompt, so the account can be created deliberately in the next
  step.
- Expect `Distribution successfully installed.` then, in `wsl -l -v`,
  `Ubuntu  Stopped  2`.

If it stops with `Wsl/InstallDistro/Service/RegisterDistro/E_ILLEGAL_STATE_CHANGE`
and *"An install, uninstall, or conversion is in progress"*, an earlier attempt
still holds the install lock: run `wsl --shutdown`, wait a few seconds, and
retry. That is exactly what happened here — the first attempt was interrupted
by a host restart mid-download, and the retry succeeded unchanged.

### Create the account (non-interactive)

`--no-launch` means no `Enter new UNIX username:` prompt. Create the account
from root instead, so the setup is reproducible:

```powershell
wsl -d Ubuntu -u root -- bash
```

```bash
useradd -m -s /bin/bash -G sudo prottoy
passwd -l prottoy        # no UNIX password: WSL never shows a login prompt
install -d -m 0755 /etc/sudoers.d
echo 'prottoy ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/90-halffirewall
chmod 0440 /etc/sudoers.d/90-halffirewall
visudo -cf /etc/sudoers.d/90-halffirewall
```

Then `/etc/wsl.conf`:

```ini
[boot]
systemd=true

[user]
default=prottoy
```

and `wsl --terminate Ubuntu` so both settings take effect.

**Why passwordless sudo.** This account is only reachable through
`wsl -d Ubuntu` on this laptop; there is no login prompt, no SSH server, and no
route in from the network. Passwordless sudo keeps every command in this
repository copy-pasteable and keeps the harness from blocking on a prompt in
the middle of a 40-probe run. If you would rather have a password, run
`sudo passwd prottoy`, then delete `/etc/sudoers.d/90-halffirewall` — and
expect `sudo` to ask for it from then on.

Verify:

```powershell
wsl -l -v                 # Ubuntu  Running  2
wsl -d Ubuntu -- whoami   # prottoy
```

If the version says `1`, run `wsl --set-version Ubuntu 2`.

## Step 4 — Install the tools

Inside Ubuntu:

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/Prottoy-pal/Default-Project.git ~/half-a-firewall
cd ~/half-a-firewall
bash scripts/wsl-setup.sh
```

`wsl-setup.sh` installs `nftables`, `iproute2`, `python3`, `python3-yaml`,
`iputils-ping`, `git`, `curl`, `jq`, then verifies four things: the binaries
exist, the kernel has an IPv6 stack, IPv6 is not disabled, and network
namespaces can be created.

Expected tail:

```
5/5  network namespaces
  OK    namespaces can be created (CAP_SYS_ADMIN present)

summary
  READY  Now run:  sudo bash scripts/check-env.sh --live
```

Installed on 28 November 2026: nftables 1.1.6, iproute2 6.19.0, Python 3.14.4,
PyYAML 6.0.3, git 2.53.0, iputils 20250605.

## Step 5 — Gate A

```bash
sudo bash scripts/check-env.sh --live
```

This builds the real lab from `bench/topology.yaml` — three namespaces joined by
two veth pairs — pings across both families, and tears it down.

You are looking for exactly these lines:

```
  PASS  IPv4 across a veth pair
  PASS  IPv6 across a veth pair
  PASS  cleaned up

  READY — lab looks good.
```

**That is Gate A. Everything after this point is measurable.** If you see either
ping failing, stop and use the troubleshooting table below — do not start
writing the harness.

Passed here on 28 November 2026, on Ubuntu 26.04.1 with kernel 6.18.58.1.
The run also checks that an `inet` table can be created, which is the table
family the whole benchmark depends on.

One WSL detail that costs time if you do not know it: `/tmp` disappears when the
distribution stops, and WSL stops it when the last process exits and
`wsl --shutdown` runs. Any pidfile or log the harness leaves under
`/tmp/halffirewall` is not durable state. The harness rebuilds it on every
`--reset`, which is why the reset is not optional.

## Step 6 — Open the repo in VS Code (optional but recommended)

On Windows, install the **WSL** extension in VS Code, then from Ubuntu:

```bash
cd ~/half-a-firewall
code .
```

VS Code opens attached to Linux: the integrated terminal is bash, Python
resolution is Linux Python, and `nft` commands work in the terminal. Edit files
here, not through `/mnt/c/...`.

---

## Where the repository should live

| Location | Verdict |
|---|---|
| `~/half-a-firewall` inside Ubuntu | **runs the lab** — native Linux filesystem, fast git, no `/mnt` bridge |
| `E:\Half-firwall` on Windows | **the writing copy** — VS Code, docs, commits, pushes |
| `/mnt/e/Half-firwall` from inside Ubuntu | avoid for lab work — every file operation crosses a slow bridge, and `nft` runs there are not measuring what you think |
| `C:\Users\User\OneDrive\...` | **retired** — OneDrive corrupts `.git` |

The two copies exchange work through GitHub, which is the synchronisation point,
not a shared folder. `docs/git-workflow.md` has the daily loop.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `WslRegisterDistribution failed with error: 0x80370102` | CPU virtualisation disabled in firmware | Reboot into BIOS/UEFI, enable **Intel VT-x** (sometimes "SVM" on AMD, "Virtualization Technology" or "Vanderpool"), save, boot |
| `wsl --status` still says virtualisation is not enabled after a reboot | `VirtualMachinePlatform` did not finish applying | Elevated PowerShell: `dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart`, then reboot again |
| `0x8007019e` | WSL optional component missing | `wsl --install --no-distribution` in elevated PowerShell, then reboot |
| `wsl --install -d Ubuntu` hangs at 0% | Microsoft Store access blocked or slow | `wsl --install -d Ubuntu --web-download` |
| `apt update` fails with "Temporary failure resolving" | WSL DNS resolver issue | `sudo rm /etc/resolv.conf && echo "nameserver 1.1.1.1" \| sudo tee /etc/resolv.conf` (temporary), or set `generateResolvConf=false` in `/etc/wsl.conf` |
| `ping` inside the lab says "Operation not permitted" | not root | every lab command needs `sudo` — the harness does this for you |
| `ip netns add` says "Operation not permitted" | WSL1, not WSL2 | `wsl --set-version Ubuntu 2` (may take a few minutes) |
| IPv6 unreachable in the lab but IPv4 works | IPv6 disabled per-interface | `sysctl net.ipv6.conf.all.disable_ipv6` must be `0`; the topology sets `accept_ra=0` deliberately |

---

## What NOT to do

- **Do not enable bridged networking or a mirrored adapter for this lab.** A
  bridged adapter would hand the VM a real IPv6 address from your ISP, and a
  configuration with defect D would expose a live host to the Internet. See
  `docs/ethics.md`.
- **Do not install a desktop environment in WSL.** It costs gigabytes, adds
  nothing, and slows every command.
- **Do not `sudo` your whole session** (`sudo -i`). Run the documented commands
  with `sudo`; keep your shell unprivileged.
- **Do not clone the repository into `/mnt/c`.** See the table above.

---

## Optional: systemd and memory limits

Not needed for the benchmark. Worth knowing if you later want Ollama to start
automatically.

`/etc/wsl.conf` inside Ubuntu:

```ini
[boot]
systemd=true
```

`C:\Users\<you>\.wslconfig` on Windows, to cap memory (default is 50% of RAM):

```ini
[wsl2]
memory=10GB
processors=8
```

Change either one, then `wsl --shutdown` in PowerShell and start Ubuntu again.
