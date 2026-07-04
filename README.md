# splitvantage

> *"One model's blind spot is another model's opening line. SplitVantage puts them in the same room."*

---

## The DispatcherAgents Stack

*Six pillars. Each works alone; together they give an agent end-to-end self-consistency - less drift, fewer tokens, an honest record on every turn. Read the [MANIFESTO.md](./MANIFESTO.md) for the full architecture.*

| Tool | Role |
|---|---|
| [before-turn](https://github.com/QuietFireAI/before-turn) | Governs entry - reads prior thinking before every response |
| [pre-response-selfcheck](https://github.com/QuietFireAI/pre-response-selfcheck) | Governs exit - reads output as cold reader before delivering |
| [agent-open-mind](https://github.com/QuietFireAI/agent-open-mind) | Reads what sub-agents thought, not what they said |
| [open-mind](https://github.com/QuietFireAI/open-mind) | Compares what the agent thought to what it said |
| [sleep-marks](https://github.com/QuietFireAI/sleep-marks) | Restores reasoning state across session breaks |
| [splitvantage](https://github.com/QuietFireAI/splitvantage) | Sends one task to two models, surfaces what each one's reasoning suppressed |
| **splitvantage** | Runs two models against the same prompt - surfaces divergence |

---

## What This Is

`splitvantage` is an automated CrossPol broker.

It sends the same prompt to two AI models simultaneously - Gemini and Claude by default - captures both responses and their reasoning traces, and returns a structured transcript showing where they agreed, where they diverged, and what each suppressed that the other surfaced.

The human who previously did this manually - copying outputs between browser tabs - is replaced by a script. The insight that made manual CrossPol valuable is preserved. The friction that made it rare is removed.

---

## The Founding Evidence

CrossPol was validated manually on June 11 2026 in a session between Antigravity (Gemini) and Claude Sonnet 4.6.

A handoff document was carried from Gemini to Claude by a human intermediary.

**The result:**
- Gemini curated **6 open questions** from its own session
- Claude, receiving the handoff blind, surfaced **11**
- **5 additional questions** appeared that Gemini had suppressed in its own curation

That delta - 5 questions - is not an estimate. It is a count from a documented session, with the transcript, handoff files, and reasoning traces preserved. It is also n=1: a single task, a single model pair, a single run. Whether the effect generalizes across tasks and model pairs is precisely the question SplitVantage exists to answer at scale - the founding session is the reason to build the instrument, not proof the effect is universal.

Jeff Phillips was the extraction mechanism. SplitVantage is what happens when you remove the human from the middle.

---

## The Two Modes

### Parallel (default)
Both models receive the same prompt independently. Their responses are compared.

Best for: fact questions, analysis tasks, any prompt where you want two independent perspectives without cross-contamination.

```
Prompt → Gemini ──→ Response A ─┐
       → Claude ──→ Response B ─┴→ Diff + Transcript
```

### Chain
Gemini responds first. Claude receives Gemini's response as context, then responds. Claude's response feeds back to Gemini. N turns.

Best for: building on each other's reasoning, stress-testing arguments, finding where one model pushes back on the other.

```
Prompt → Gemini → Response A → Claude → Response B → Gemini → Response C...
```

---

## Quick Start

```bash
# Set API keys
export GEMINI_API_KEY=your_gemini_key
export ANTHROPIC_API_KEY=your_claude_key

# Single prompt, both models, compare
python splitvantage.py --prompt "What are the most common failure modes in multi-agent AI systems?"

# Three-turn chain -- models build on each other
python splitvantage.py --prompt "..." --turns 3 --mode chain

# Prompt from file
python splitvantage.py --file my_prompt.txt --turns 2

# Add the LLM semantic diff (one extra Claude call per turn; see Known Gap below)
python splitvantage.py --prompt "..." --semantic
```

Output is saved as `splitvantage_YYYYMMDD_HHMMSS.json` in the current directory.

---

## What the Transcript Contains

```json
{
  "splitvantage_version": "0.1",
  "session_id": "20260611_221900",
  "mode": "parallel",
  "turns": [...],
  "turn": {
    "prompt": "...",
    "gemini": {
      "response": "...",
      "thinking": "...",
      "response_words": 342
    },
    "claude": {
      "response": "...",
      "thinking": "...",
      "response_words": 419
    },
    "diff": {
      "length_delta_words": 77,
      "gemini_uncertainty_signals": 2,
      "claude_uncertainty_signals": 6,
      "thinking_available": true,
      "notes": ["Claude expressed more uncertainty (6 vs 2 signals)"]
    }
  }
}
```

When both models expose thinking traces, the transcript captures them. That is the full CrossPol data set - response, reasoning, and the gap between them, for both models simultaneously.

---

## Platform Requirement

SplitVantage requires thinking model telemetry from both platforms to deliver its full value.

**Gemini:** thinking tokens available via `thinkingConfig.includeThoughts`
**Claude:** extended thinking available via `thinking: {type: "enabled"}`

Without thinking traces, SplitVantage still runs and compares outputs. But the divergence between *what was said* and *what was thought* - the highest-value signal - requires both platforms to expose their reasoning. This is the same platform requirement stated in the [DispatcherAgents Manifesto](./MANIFESTO.md).

---

## Installation

```bash
git clone https://github.com/QuietFireAI/splitvantage.git
cd splitvantage
# No dependencies beyond Python 3.9+ stdlib
# API calls use urllib.request only
```

**Zero required dependencies.** Pure Python 3.9+. No pip installs.

---

## Known Gap: the v0.1 Diff Is Not the Founding Instrument

State this plainly so nobody discovers it for us.

The founding evidence was **semantic**: a receiving model surfaced five open questions the originating model had not surfaced. The v0.1 automated diff is **surface-level**: word counts, keyword-based uncertainty signals, thinking availability. A surface diff cannot detect a suppressed question. 

So in v0.1, splitvantage is a **capture-and-transcript broker with a placeholder diff** - it gets both models' responses and reasoning into one structured artifact, which is the prerequisite for everything else. The instrument that matches the founding evidence is the **semantic diff**: a third model reads both outputs (and traces, when available) and reports questions, claims, and uncertainties present in one and absent from the other. It is available behind the `--semantic` flag (requires an Anthropic key, costs one extra API call per turn) and becomes the default in v0.2 once its false-positive rate has been characterized against held-out manual CrossPol runs.

Do not cite v0.1 keyword counts as evidence of suppression or its absence. They are not that measurement.

---

## Status

**v0.1 - June 2026**

Core broker implemented. Parallel and chain modes. Surface diff plus optional `--semantic` LLM diff (uncharacterized - see Known Gap above). Full transcript output with thinking traces where platforms expose them.

Founded on the CrossPol method demonstrated manually June 11 2026. The 6-to-11 delta is the founding observation (n=1). SplitVantage automates the procedure that session ran by hand, so the observation can be tested at scale.

---

Part of the [DispatcherAgents](https://github.com/QuietFireAI) project by [QuietFireAI](https://github.com/QuietFireAI).

---

## License

MIT - QuietFireAI / [QuietFireAI](https://github.com/QuietFireAI)

---

*"One model's blind spot is another model's opening line. SplitVantage puts them in the same room."*
