# Etapa 9c — diagnostic switches from one-question-per-turn to a single form batch

Status: **implemented**, motivated by a real cost measurement during Etapa 9 item 2
(the multi-agent work proposal's trilha cost/quality measurement,
`proposta-trabalho-multiagente-claude.md` section 8).

## What changed

`instructions/20-diagnostic.md`'s original design (Etapa 4b,
`docs/claude-agent-pilot-etapa4b-diagnostic-design.md`) asked exactly one
question per `issue_comment` turn — genuinely adaptive, each question chosen
after seeing the previous answer. That is still a defensible design on
placement-quality grounds alone. The reason it changed is cost, measured
against a real session, not a guess:

| turn | what happened | real cost |
|---|---|---|
| 1 | initial comment -> question 1 | $0.0666 |
| 2 | a duplicate non-answer comment -> re-asked question 1 | $0.1250 |
| 3 | answer 1 -> question 2 | $0.0254 |
| 4 | answer 2 -> question 3 | $0.0298 |
| 5 (terminal) | answer 3 -> author concludes | $0.0776 |
| 5 (terminal) | independent reviewer | $0.1571 |
| **total** | | **≈ $0.4815** |

That is roughly **4x** `bootstrap_instance`/`configure_intake`/`intake`, which
each landed around $0.11–0.12 in the same session. The reason isn't the
number of questions — it's that `scripts/build_diagnostic_context.py`
reconstructs the *entire* comment thread from scratch on every single turn,
so cache-read tokens (and cost) grow with every question instead of staying
flat. A second finding made this worse in practice: `state/agent-pilot-usage.jsonl`
only ever logs the terminal turn's cost (the reviewer job, which is the only
one that runs `scripts/summarize_agent_pilot_usage.py`) — every non-terminal
turn's real spend, including the $0.1250 wasted on a duplicate non-answer
comment, was invisible in the repository's own cost record and only
recoverable by hand from each run's raw Actions log. That gap is not fixed by
this change and remains open (see "Not addressed here" below).

## The new design

`instructions/20-diagnostic.md`'s "Interaction style" section now asks the
whole question set in one turn and evaluates the single combined reply in
the next:

- **Turn 1:** choose the question count from the existing budget table
  (unchanged), post every question together as one numbered list, state the
  total count up front. Do not wait for answers one at a time.
- **Turn 2 (terminal):** evaluate the entire reply at once, exactly like the
  old terminal turn did, and finish -- write the summary, run the review,
  complete.
- **Optimization:** if the trigger comment itself already contains complete,
  unprompted answers, skip straight to evaluation in turn 1.
- **No third round.** If the single reply leaves a genuine gap, that becomes
  `evidence_sufficiency: limited` and a caveat, not a follow-up question --
  the same hard-maximum fallback the old design already had, just reached
  after one round instead of several.

This bounds a normal placement to exactly two agent-pilot dispatches (down
from as many as `hard_max + 1`), and an unusually complete first reply to
one. `.github/workflows/agent-pilot-diagnostic.yml` needed no functional
change -- the trigger, the loop-prevention/scope guards, and "an empty diff
from a non-terminal turn is not a failure" all still hold exactly as before.
Only the instructions' question-asking philosophy changed.

`schemas/diagnostic-summary.schema.json` needed no change either --
`method` is already a free-form string; sessions using this design should
record `"single_form_batch"` there, which is enough for a future dispatch to
tell old- and new-style sessions apart in `state/agent-pilot-usage.jsonl` or
manual cost samples.

## Not addressed here

The per-turn cost invisibility finding above (only the terminal turn's cost
reaches `state/agent-pilot-usage.jsonl`) is a real, separate gap. It matters
less now that a normal session is only two turns instead of five-plus, but
it isn't fixed by this change and remains open for a future etapa.
