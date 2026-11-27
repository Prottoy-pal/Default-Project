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
| Disk free | 125.8 GB on C: | fine |
| Virtualisation | hypervisor already running (Memory Integrity) | fine |
| WSL package | **3.0.5 installed** | done |
| `VirtualMachinePlatform` | **enabled** | done |
| Ubuntu distribution | not installed yet | **next** |
| Reboot | **pending** | **required** |

Steps 1 and 2 below are already complete. Start at step 3.

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

## Step 3 — Register Ubuntu

Open PowerShell (normal, not elevated) and run:

```powershell
wsl --install -d Ubuntu
```

It downloads roughly 500 MB and then asks for two things:

```
Enter new UNIX username:
New password:
Retype new password:
```

Rules for these:

- The username is **lowercase, no spaces** — e.g. `prottoy`. It is not your
  Windows name and does not need to match it.
- The password **does not echo** while you type. That is normal. Nothing appears
  at all, not even asterisks.
- This password becomes `sudo`. Pick something you will remember; there is no
  password-reset button.

When it finishes you land in a shell like:

```
prottoy@DESKTOP-XXXX:~$
```

Verify the version:

```bash
wsl.exe -l -v      # STATE: Running, VERSION: 2
```

If it says `VERSION 1`, run `wsl --set-version Ubuntu 2`.

## Step 4 — Install the tools

Inside Ubuntu:

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/Prottoy-pal/Default-Project.git ~/half-a-firewall
cd ~/half-a-firewall
bash scripts/wsl-setup.sh
```

`wsl-setup.sh` installs `nftables`, `iproute2`, `python3`, `curl`, `jq`, then
verifies four things: the binaries exist, the kernel has an IPv6 stack, IPv6 is
not disabled, and network namespaces can be created.

Expected tail:

```
summary
  READY  Now run:  sudo bash scripts/check-env.sh --live
```

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
| `~/half-a-firewall` inside Ubuntu | **use this** — native Linux filesystem, fast git, and no OneDrive in the path |
| `C:\Users\User\...\Default Project` | keep as a Windows backup of the writing, but do not run the lab here |
| `/mnt/c/Users/...` from inside Ubuntu | avoid — every file operation crosses a slow bridge, and git is noticeably unreliable there |

The lab work (namespaces, nftables, probes, model outputs) belongs in the Linux
home directory. The GitHub remote is the synchronisation point between the two
copies, not a shared folder.

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
