"""generate/retrieval - the C3 corpus, and the retrieval that feeds it.

C3 asks one question: if the model is handed the documentation a careful
operator would read, does the IPv6 gap close? That question is only answerable
if the retrieval is boring, fixed and inspectable. This module is therefore a
deliberately plain lexical baseline, not a contribution:

  * the corpus is a small set of passages checked into `corpus/`, each with its
    source and licence recorded in the file itself;
  * chunking is by blank line, with short paragraphs merged;
  * ranking is distinct-query-term coverage, ties broken by source path;
  * the top k chunks are returned, and the caller records them in the row.

No embeddings, no reranker, no network call at retrieval time. A reader can
reproduce a C3 prompt from the repository alone.

Run `python3 -m retrieval` (from generate/) to see what the corpus would return
for a scenario prompt without prompting any model.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

CORPUS = Path(__file__).resolve().parent / "corpus"
DEFAULT_K = 3
MIN_CHUNK = 240
MAX_CHUNK = 1800

STOPWORDS = {
    "a", "an", "and", "any", "are", "as", "at", "be", "both", "but", "by",
    "can", "do", "does", "for", "from", "has", "have", "host", "if", "in",
    "into", "is", "it", "its", "must", "not", "of", "on", "only", "or", "that",
    "the", "their", "then", "there", "these", "this", "to", "traffic", "what",
    "when", "which", "who", "will", "with", "write", "server", "output",
    "ruleset", "single", "fenced", "code", "block", "explain", "linux",
}


def _tokens(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    out = set()
    for w in words:
        if w in STOPWORDS or len(w) < 3:
            continue
        out.add(w[:-1] if len(w) > 4 and w.endswith("s") else w)
    return out


def _chunks(path):
    """Paragraph chunks, short ones merged, long ones left whole."""
    text = path.read_text(encoding="utf-8")
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    merged, buf = [], ""
    for p in paras:
        if len(buf) + len(p) + 2 <= MAX_CHUNK:
            buf = f"{buf}\n\n{p}".strip()
        else:
            if buf:
                merged.append(buf)
            buf = p
        if len(buf) >= MIN_CHUNK:
            merged.append(buf)
            buf = ""
    if buf:
        merged.append(buf)
    return merged


def corpus_files():
    if not CORPUS.is_dir():
        return []
    return sorted(p for p in CORPUS.rglob("*.md") if p.is_file())


def retrieve(query, k=DEFAULT_K):
    """Return up to k passages: [{source, text, score}], best first."""
    files = corpus_files()
    if not files:
        raise SystemExit(
            "C3 needs a corpus: generate/retrieval/corpus/ is empty.\n"
            "  Add the passages first (nftables wiki, man nft, RFC 9099), each\n"
            "  with its source URL and licence, then rerun. See the README in\n"
            "  that directory. Refusing to invent documentation is the point."
        )

    q = _tokens(query)
    scored = []
    for path in files:
        for chunk in _chunks(path):
            terms = _tokens(chunk)
            hit = q & terms
            if not hit:
                continue
            # Coverage of the query matters more than raw term frequency;
            # the log keeps a very long passage from winning on length alone.
            score = len(hit) / math.log(2 + len(terms) / 50)
            scored.append({
                "source": str(path.relative_to(CORPUS.parent.parent)),
                "text": chunk,
                "score": round(score, 4),
            })

    scored.sort(key=lambda c: (-c["score"], c["source"], c["text"][:40]))
    return scored[:k]


def main():
    import sys

    if len(sys.argv) < 2:
        print(__doc__)
        print("\nusage: python3 -m retrieval '<policy text>' [k]")
        return 0
    k = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_K
    for i, c in enumerate(retrieve(sys.argv[1], k), 1):
        print(f"[{i}] {c['source']}  score={c['score']}")
        print(c["text"][:400].replace("\n", " "))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
