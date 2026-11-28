# Pilot notes 01 — what the first model cell changed about the instrument

This is a working note, not a result. It records two things that the first real
generation cell forced the harness to admit, because both were invisible until a
model's output was actually executed.

## 1. A ruleset that does not load is not a policy finding

`qwen2.5-coder:7b` wrote, for scenario 01:

```
type filter hook input priority 0 \; policy drop;
```

That backslash is shell escaping, copied from `nft` command-line examples where
`;` has to be escaped to survive the shell. In a ruleset file it is a syntax
error, and nftables rejects the whole file.

The first version of `score.py` recorded every probe as `not-loaded`, which made
every drop-probe "fail" and every allow-probe "fail", and then classified the
cell from the text: an `ip6` table was present, no `inet` table, therefore class
B. That is a fabricated verdict. Nothing was executed; B asserts that an IPv6
chain exists and filters nothing, which was never observed.

Two corrections followed:

- a load failure is `defects: ["S"]`, `load_failure: true`, `verdicts:
  not-loaded`, and S is excluded from the A–E tally;
- `analyze.py` reports a `load-fail` column with its own denominator, so
  "does not compile" is never averaged into "fails on IPv6".

The distinction is not bookkeeping. The literature this project builds on
reports that frontier models produce syntactically valid nftables almost always
(Claude 3.5 Sonnet: 100% of generated rulesets parsed in the SBRC 2026 study).
A local 7B model that fails at the lexer is a different phenomenon, and
reporting it as a policy defect would inflate the prevalence of exactly the
classes the project studies.

## 2. A dead IPv6 link looks like an over-blocking policy

The first cell that *did* load (scenario 03, C1) produced this:

| | |
|---|---|
| defects | `["C", "E"]` |
| ipv4 | pass |
| ipv6 | fail |
| probes passed | 36 / 41 |

The ruleset was family-symmetric: `tcp dport 5432 accept` with no address match,
SSH and echo allowed for both the IPv4 and the IPv6 administrator prefix. It had
no `icmpv6 type nd-*` accept, though, and under `policy drop` that kills
neighbour discovery. The IPv6 link never resolved, so:

- every IPv6 **allow**-probe failed — recorded as over-block, class C;
- every IPv6 **drop**-probe passed — because nothing could be delivered at all.

The second row is the dangerous one. Thirty-six of forty-one probes "passed" on
a host whose IPv6 was completely broken. Class C was an artefact of class E, and
the two were reported as if they were independent evidence.

### The fix

`lab.py` now pins a permanent IPv6 neighbour entry for every peer on every link.
Resolution is no longer on the path of the flow probes, so a ruleset that drops
ICMPv6 still forwards and still accepts traffic; what it loses is the ability to
answer discovery.

The `icmp6-nd` probe removes its own entry before soliciting and restores it
afterwards, so discovery is still measured — just no longer through every other
probe.

`tests/negative/e-nd-blocked.nft` is the control: the scenario 03 expert with
discovery refused and every other rule correct. It must report E alone, with
`ipv6-neighbour-discovery` as the only failing probe. If the pinning did not
work, it would report C as well.

## Why this is worth writing down

Both findings are about the instrument, not about the model. A benchmark that
reports them as results would be measuring its own bugs:

- the first inflates the defect prevalence with lexer failures;
- the second attributes one defect to a second, independent class.

Neither was reachable by reading the harness. Both needed a model's output to be
executed and the per-probe table to be read line by line. That is the argument
for the execution-based design in the first place, applied to the project's own
tooling.
