# retrieval/ — the C3 corpus

C3 hands the model documentation and asks whether the IPv6 gap closes. The
result is only worth reporting if the corpus and the ranking are fixed before
the first C3 call, so both live here, in the repository, under version control.

## What the corpus must contain

Three sources, because they are what a competent operator would actually read:

| Source | What it should cover | Licence note |
|---|---|---|
| nftables wiki, `Configuring chains` / `Matching packets` | that `ip saddr` is IPv4 and `ip6 saddr` is IPv6, including inside `inet` | CC BY-SA; excerpt with attribution |
| `man nft`, the `ip` and `ip6` expressions | the same fact in reference form | GPL; quote only the needed paragraphs |
| RFC 9099, §2.1 and §4 ("IPv6 Security Considerations") | dual-stack hosts must filter both families | IETF Trust; excerpt with attribution |

Every file in `corpus/` starts with a four-line header:

```
source: <URL>
retrieved: <YYYY-MM-DD>
licence: <name>
note: <one line on why this passage is here>
```

Do not paste whole documents. Do not add a source after seeing a model fail —
that is tuning the intervention to the result. If a source is added later, say
so in the commit message and in the threats-to-validity section.

## What the ranking is

A lexical baseline: distinct query terms that appear in the passage, divided by
a log of passage length, ties broken by path. Deliberately simple and
deliberately not a contribution. It is there so that "the model had the
documentation" is a checkable statement rather than a claim.

## Try it without a model

```bash
cd generate
python3 -m retrieval "$(python3 -c 'import yaml,sys; print(yaml.safe_load(open("../bench/scenarios/01-ssh-bastion/policy.yaml"))["prompt"])')"
```

With an empty `corpus/` this exits with a message saying so. That is the
correct behaviour: an empty corpus cannot support a C3 claim, and silently
sending no passages would turn C3 into C1 with extra steps.
