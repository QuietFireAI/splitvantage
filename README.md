# splitvantage

> *"One model's blind spot is another model's opening line. SplitVantage puts them in the same room."*

---

## The DispatcherAgents Stack

*Each tool works alone. All five make generation governed. Read the [MANIFESTO.md](./MANIFESTO.md) for the full architecture.*

| Tool | Role |
|---|---|
| [before-turn](https://github.com/QuietFireAI/before-turn) | Governs entry -- reads prior thinking before every response |
| [pre-response-selfcheck](https://github.com/QuietFireAI/pre-response-selfcheck) | Governs exit -- reads output as cold reader before delivering |
| [agent-open-mind](https://github.com/QuietFireAI/agent-open-mind) | Reads what sub-agents thought, not what they said |
| [open-mind](https://github.com/QuietFireAI/open-mind) | Compares what the agent thought to what it said |
| [sleep-marks](https://github.com/QuietFireAI/sleep-marks) | Restores reasoning state across session breaks |
| **splitvantage** | Runs two models against the same prompt -- surfaces divergence |

---

## What This Is

`splitvantage` is an automated CrossPol broker.

It sends the same prompt to two AI models simultaneously -- Gemini and Claude by default -- captures both responses and their reasoning traces, and returns a structured transcript showing where they agreed, where they diverged, and what each suppressed that the other surfaced.

The human who previously did this manually -- copying outputs between browser tabs -- is replaced by a script. The insight that made manual CrossPol valuable is preserved. The friction that made it rare is removed.

---

## The Founding Evidence

CrossPol was validated manually on June 11 2026 in a session between Antigravity (Gemini) and Claude Sonnet 4.6.

A handoff document was carried from Gemini to Claude by a human intermediary.

**The result:**
- Gemini curated **6 open questions** from its own session
- Claude, receiving the handoff blind, surfaced **11**
- **5 additional questions** appeared that Gemini had suppressed in its own curation

That delta -- 5 questions -- is not an estimate. It is a measured result from a documented session. The session transcript, handoff files, and reasoning traces are all preserved.

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

When both models expose thinking traces, the transcript captures them. That is the full CrossPol data set -- response, reasoning, and the gap between them, for both models simultaneously.

---

## Platform Requirement

SplitVantage requires thinking model telemetry from both platforms to deliver its full value.

**Gemini:** thinking tokens available via `thinkingConfig.includeThoughts`
**Claude:** extended thinking available via `thinking: {type: "enabled"}`

Without thinking traces, SplitVantage still runs and compares outputs. But the divergence between *what was said* and *what was thought* -- the highest-value signal -- requires both platforms to expose their reasoning. This is the same platform requirement stated in the [DispatcherAgents Manifesto](./MANIFESTO.md).

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

## Status

**v0.1 - June 2026**

Core broker implemented. Parallel and chain modes. Diff analysis. Full transcript output with thinking traces.

Founded on the CrossPol method validated June 11 2026. The 6-to-11 delta is the founding evidence. SplitVantage automates what that session proved by hand.

Part of the [DispatcherAgents](https://dispatcheragents.com) project by [QuietFireAI](https://github.com/QuietFireAI).

---

*"Jeff Phillips was the extraction mechanism. This is what happens when you remove the human from the middle."*

