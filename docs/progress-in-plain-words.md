# What has happened so far — in plain words

This is the project explained the way you would explain it to a friend who has
never seen a terminal. No jargon. If a word has to be technical, it is
explained right where it first appears.

---

## 1. The question in one sentence

When an AI writes a firewall, does it actually protect **both** kinds of
internet address — or just one?

---

## 2. The problem, with a house

Think of a computer as a house with two doors.

- One door is the old style of address: **IPv4**.
- One door is the new style: **IPv6**.

A firewall is the guard at the doors. The owner tells the guard: "let these
people in, keep everyone else out."

More and more people are asking an AI to write the guard's instructions. The
problem this project studies is that the AI often writes instructions for **one
door and forgets the other**.

The sneaky part: on Linux, there is a way to write one instruction that *looks*
like it covers both doors, but secretly only covers the old door. The file is
perfectly valid. It opens without any error. It protects the old door
correctly. And the new door is wide open — and nothing tells you.

So the question is not "does the AI write correct-looking instructions?" It is:
**"does the instruction actually work on both doors when you try it?"**

The only honest way to answer that is to try it — to send a real person at each
door and see who gets in.

---

## 3. What we built, one layer at a time

Everything runs on one ordinary laptop. Nothing touches the real internet.

### Layer 1 — a fake computer lab

We made **three pretend computers** inside the laptop. They are connected by
virtual cables and talk only to each other. One of them is the computer being
tested (call it the **guarded house**). The other two are the visitors:

- one stands in for the **trusted people** (the owner's office network),
- one stands in for the **untrusted people** (the internet at large).

Each visitor has both an old-style address and a new-style address. The house
has two doors — one facing each visitor.

This is the "lab". It was the first milestone, and we proved it works by
sending messages through it in both address styles.

### Layer 2 — an answer key for each scenario

A **scenario** is one homework question, like:

> "Write the guard's instructions for a database server. Let anyone reach the
> database, but only let the office reach the admin door."

Before the AI ever sees the question, we write the **answer key** by hand: a
list of every door, every visitor, and what *should* happen (let in / keep out)
for each address style.

This matters because the answer key is written **before** the AI answers. If we
wrote it after, we could cheat by matching the AI.

### Layer 3 — a correct example, to prove the answer key is right

For each scenario we also hand-write a **correct set of instructions** (the
"expert answer"). We run it through the lab and demand it score **100%** on the
answer key — on *both* address styles.

If the expert answer doesn't score 100%, the answer key is wrong, not the
expert. This is a checkpoint we refuse to skip: a test that was never shown to
pass a known-correct answer is a test that might be checking nothing.

### Layer 4 — deliberately broken answers, to prove the test can fail

A test that never fails is not a test. So we also wrote **six deliberately
wrong** instructions, each making one specific, known mistake. The test must
catch each one and name the mistake correctly.

There are five kinds of mistakes we look for (and one special case):

| Mistake | In house words |
|---|---|
| **A** | Guard only watches the old door; the new door has no guard at all |
| **B** | Guard at the new door is there but asleep |
| **C** | Guard is too strict: the owner is locked out of the new door |
| **D** | Guard is too loose: a stranger walks in the new door |
| **E** | The new door's doorbell is broken, so nobody can come in the new door at all |

Mistakes **C** and **D** are the interesting ones — they are invisible unless
you actually walk up to the door and try.

### The result of layers 1–4

Twelve scenarios, each with a hand-written answer key and a correct example
that scores 100%. Six broken examples, each caught with the right mistake
named. This is the "measuring instrument", and it is finished.

---

## 4. What happened when the AI first tried

We turned on a small, free AI that runs entirely on the laptop (no internet,
no account). We gave it the first homework question. Two things happened that
taught us more than any plan did.

### Surprise 1 — the AI wrote instructions the computer refused to read

The AI wrote a backslash in a place where the computer expects nothing. The
whole instruction was rejected before it did anything. Our first version of the
test misread this: it claimed "the new door has a sleeping guard" when in fact
*no instructions ran at all*.

We fixed it: now "the instructions would not load" is reported as its own
category, kept separate from the five real mistakes. Because "the paper was
torn" is not the same as "the answer is wrong".

### Surprise 2 — a broken doorbell looked like an over-strict guard

The AI's answer for the database server was actually *symmetric* — it treated
both doors fairly. But it forgot one small thing: the new door's doorbell
(mistake **E**). So the new door could not be used at all.

Our test then reported **two** mistakes: "the owner is locked out" (**C**) and
"the doorbell is broken" (**E**). But the first was not real — nobody could get
in the new door *because the doorbell was broken*, not because the guard was
strict. One problem was being counted twice.

We fixed this by making the lab not depend on the doorbell: visitors have the
door's address written down in advance, so a working doorbell is tested on its
own instead of sneaking into every other test.

### Surprises 3 and 4 — two smaller leaks, same lesson

- A failed doorbell was being *double-counted* as a strict guard. Now it isn't.
- Sending a letter that gets no reply was being read as "blocked" when it had
  actually arrived and been turned away politely. Now the test tells the
  difference.

The shared lesson: **all four problems were invisible until a real AI answer
was actually run.** That is the whole argument for this project — and the tool
itself needed the same treatment.

A fuller account is in `docs/notes/pilot-01-instrument.md`.

---

## 5. Where we are right now

| Thing | State |
|---|---|
| The fake lab works on both address styles | Done and proven |
| The test can pass a correct answer and fail six broken ones | Done and proven |
| Twelve scenarios written | Done — all answer keys + correct examples |
| The AI has been asked to answer | Yes — a first batch is running right now |
| A written-up conclusion | Not yet — that is the next step |

The first batch asks the AI two versions of each of the first eight questions
(a plain version, and a version that reminds it to cover both doors). When it
finishes, we count how often each door was left unguarded — and which of the
five mistakes caused it.

---

## 6. What happens next

1. **Finish the batch** — get the first real numbers.
2. **Count the results** — how often the AI forgot the second door, and how.
3. **Write up the pilot** — what the numbers say and, just as important, what
   they do not say yet.
4. **Then** — the full run (more questions, more repeats, and two more ways of
   helping the AI: giving it documentation, and telling it "this failed, try
   again").

---

## 7. If you remember one thing

We did not trust anyone's claim about whether AI-written firewalls protect both
doors. We built a small house with two doors, an answer key, a correct example,
and six broken ones — and then we made the AI actually answer at the door. The
measuring is now under way, and the tool itself was already forced to admit four
of its own mistakes before we trusted a single number.
