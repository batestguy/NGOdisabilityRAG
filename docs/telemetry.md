# What DRLCA records (H7 improvement signal)

*For the owner's review before deploy. This is the full list; if it is not here, it is not recorded.*

## Where it goes
Each line is printed to the app's **standard output**, which Render keeps in its **service logs**
(Render dashboard → the service → Logs; search `DRLCA_SIGNAL`). There is **no other service, no
analytics SDK, no file and no network call**. Render's log retention and access rules apply; nobody
else receives these lines. To keep any counts beyond Render's retention, copy the lines out and run
`scripts/summarise_signal.py` (it reads pasted lines; it sends nothing anywhere).

## The two kinds of line

**1. When a new answer is produced** (once per question; never again when the page re-draws):

| field | meaning | example |
|---|---|---|
| `id` | a random token for this one answer, only used to join it to line 2 | `63682abd59a7` |
| `route` | which part answered | `legal`, `help`, `greeting`, `clarify` |
| `refused` | whether the legal search found nothing usable | `false` |
| `top` | a coarse band of the best excerpt score, never the score itself | `0.20-0.30` |
| `shown` | how many law excerpts were shown | `9` |
| `orgs` | how many organisations were shown (helplines are not counted) | `3` |
| `ai` | whether an AI-written answer was produced | `false` |

**2. When someone answers "Was this answer helpful?"**: the same `id` and `helpful` = `yes` / `no`.

## What is NEVER recorded
* **The words of the question**, unless the person ticks **"Also share the words of my questions"**
  in the sidebar (off by default). Then only each *new* question's text, cut to 300 characters, is
  added to line 1 as `q`. Unticking it stops this immediately.
* **The conversation history**, any answer text, excerpts, citations or organisation names.
* **Any identifier of the person**: no session id, no user id, no IP address, no cookie, no
  browser or device details. (Render's own request logs are separate and not part of this.)

## What users see
Under every answer: the "Was this answer helpful?" choice (nothing selected until they pick) and
this note:

> Your yes/no is counted with: which route answered (law or help), whether it was refused, a score
> band, and how many excerpts or contacts were shown. Not your question and not your conversation,
> unless you switch on "Also share the words of my questions" in the sidebar.

## Why
The deferred retrieval work (dense retrieval, fine-tuning, Pidgin) was waiting for real usage
rather than guessed test sets. Counts of route, refusals and "helpful" answers are enough to choose
the next experiment without holding anyone's words.

*Enforced by `scripts/test_phase09_ops.py` (H7 block): one stdout line, no question text without
the opt-in, only the fields above, no network or file use, never on replay.*
