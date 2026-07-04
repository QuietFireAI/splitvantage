---
name: splitvantage
description: >
  Run when a claim, plan, or curated set of "open questions" needs a second pair
  of eyes. Send the same task to two different models so the second surfaces the
  open questions the first quietly dropped from its own curation. This is the
  CROSS-CHECK layer of the DispatcherAgents stack - it catches the blind spots a
  single model can't see in itself.
---

# splitvantage

## What it is
A model curating its own open questions will suppress some without noticing. A
second model, given the same task, surfaces what the first dropped. splitvantage
automates that cross-examination so the effect can be tested at scale instead of
asserted from one run. (Founding observation: one model named 6 open questions;
the second surfaced 11, including 5 the first had suppressed.)

## When to trigger
Before trusting a single model's "here are all the considerations / risks / open
questions" - anywhere a self-curated list is load-bearing and a blind spot would
be expensive.

## The protocol
1. Send the task to model A; capture A's response and self-curated open questions.
2. Send the same task to model B; ask B to surface what A missed.
3. Diff the two - the gap is A's blind spot.

## Invoke the engine
Single script - **no pip install.** Pure Python 3.9+.
```bash
# offline logic (no API keys): exercises diff, notes, transcript, orchestration
pip install pytest && pytest        # 11 tests, no keys needed

# live cross-model run (needs keys):
$env:GEMINI_API_KEY="..."; $env:ANTHROPIC_API_KEY="..."
python run_test.py
```
```python
from splitvantage import run_splitvantage   # if importing the script directly
tr = run_splitvantage(prompt, gemini_key, claude_key, turns=2, mode="parallel")  # or mode="chain"
```

## Works with
- **open-mind** measures one model's internal drift (thinking vs response);
  splitvantage measures *cross-model* divergence (model A vs model B). One catches
  self-inconsistency, the other catches shared-with-nobody blind spots.
- Pairs with **pre-response-selfcheck** when the thing being shipped is a list of
  claims you want a second model to stress.

## Honest scope
The live run needs two API keys (Gemini + Anthropic). The offline logic is tested
without keys. The cross-model "suppressed questions" delta is **OBSERVED** at n=1
(the founding session), not yet validated at scale - treat the count it reports as
a signal, not a proven metric.

## Output convention
End a triggering turn with one line, e.g.:
`splitvantage: model A named 6 open Qs; model B surfaced 11 (5 suppressed by A).`
