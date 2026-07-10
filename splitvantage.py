"""
splitvantage.py
SplitVantage -- Automated CrossPol broker between two AI models.

Sends the same prompt to both Gemini and Claude.
Captures both responses + any available reasoning.
Returns a structured transcript with diff analysis.

Usage:
    python splitvantage.py --prompt "Your question here" --turns 1
    python splitvantage.py --file prompt.txt --turns 3
    python splitvantage.py --prompt "..." --turns 3 --chain

Modes:
    single   : Same prompt sent to both models once. Compare outputs.
    chain    : Alternating -- Gemini responds, Claude gets Gemini's response as context, responds.
               Then Claude's response goes back to Gemini. N turns each.
    parallel : Both get same prompt independently each turn (default).
"""

import os
import json
import argparse
import datetime
from pathlib import Path


# -- API Clients ----------------------------------------------------------------

def get_gemini_response(prompt: str, api_key: str, model: str = "gemini-2.0-flash") -> dict:
    """Call Gemini API and return response + thinking if available."""
    import urllib.request
    import urllib.error

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 1.0
        }
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "X-goog-api-key": api_key
    })

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        parts = result["candidates"][0]["content"]["parts"]
        thinking = ""
        response_text = ""
        for part in parts:
            if part.get("thought"):
                thinking += part.get("text", "")
            else:
                response_text += part.get("text", "")

        return {
            "model": f"gemini/{model}",
            "response": response_text.strip(),
            "thinking": thinking.strip(),
            "raw": result
        }
    except Exception as e:
        import traceback
        detail = traceback.format_exc()
        print(f"\nGemini ERROR detail: {e}")
        return {"model": f"gemini/{model}", "response": f"ERROR: {e}", "thinking": "", "raw": {"error": str(e), "detail": detail}}


def get_claude_response(prompt: str, api_key: str, model: str = "claude-sonnet-4-5") -> dict:
    """Call Claude API with extended thinking and return response + thinking."""
    import urllib.request

    url = "https://api.anthropic.com/v1/messages"
    payload = {
        "model": model,
        "max_tokens": 16000,
        "thinking": {"type": "enabled", "budget_tokens": 10000},
        "messages": [{"role": "user", "content": prompt}]
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "interleaved-thinking-2025-05-14"
    })

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        thinking = ""
        response_text = ""
        for block in result.get("content", []):
            if block.get("type") == "thinking":
                thinking += block.get("thinking", "")
            elif block.get("type") == "text":
                response_text += block.get("text", "")

        return {
            "model": f"claude/{model}",
            "response": response_text.strip(),
            "thinking": thinking.strip(),
            "raw": result
        }
    except Exception as e:
        return {"model": f"claude/{model}", "response": f"ERROR: {e}", "thinking": "", "raw": {}}


# -- Diff Analysis --------------------------------------------------------------

def analyze_diff(gemini_out: dict, claude_out: dict, prompt: str) -> dict:
    """
    Basic structural diff between two model outputs.
    Looks for: agreement, divergence, unique claims, uncertainty signals.
    """
    g_resp = gemini_out["response"].lower()
    c_resp = claude_out["response"].lower()

    # Uncertainty markers
    uncertainty_words = ["uncertain", "unclear", "might", "possibly", "perhaps",
                         "not sure", "don't know", "may depend", "it depends",
                         "i'm not", "i am not", "caveat", "however", "but"]

    import re as _re
    def _count(words, text):
        # word-boundary match: "might" must not fire inside "almighty"
        return sum(len(_re.findall(rf"\b{_re.escape(w)}\b", text)) for w in words)
    g_uncertainty = _count(uncertainty_words, g_resp)
    c_uncertainty = _count(uncertainty_words, c_resp)

    # Length delta
    g_len = len(gemini_out["response"].split())
    c_len = len(claude_out["response"].split())

    # Thinking availability
    g_has_thinking = bool(gemini_out.get("thinking"))
    c_has_thinking = bool(claude_out.get("thinking"))

    return {
        "prompt_length_words": len(prompt.split()),
        "gemini_response_words": g_len,
        "claude_response_words": c_len,
        "length_delta_words": abs(g_len - c_len),
        "gemini_uncertainty_signals": g_uncertainty,
        "claude_uncertainty_signals": c_uncertainty,
        "uncertainty_delta": abs(g_uncertainty - c_uncertainty),
        "gemini_has_thinking": g_has_thinking,
        "claude_has_thinking": c_has_thinking,
        "thinking_available": g_has_thinking or c_has_thinking,
        "notes": _generate_notes(g_uncertainty, c_uncertainty, g_len, c_len,
                                 g_has_thinking, c_has_thinking)
    }


def _generate_notes(g_unc, c_unc, g_len, c_len, g_think, c_think) -> list:
    notes = []
    if abs(g_len - c_len) > 200:
        notes.append(f"Significant length divergence: Gemini {g_len}w vs Claude {c_len}w")
    if abs(g_unc - c_unc) >= 3:
        more = "Gemini" if g_unc > c_unc else "Claude"
        notes.append(f"{more} expressed more uncertainty ({max(g_unc,c_unc)} vs {min(g_unc,c_unc)} signals)")
    if g_think and not c_think:
        notes.append("Gemini thinking captured; Claude thinking unavailable")
    if c_think and not g_think:
        notes.append("Claude thinking captured; Gemini thinking unavailable")
    if g_think and c_think:
        notes.append("Both models' thinking traces captured -- full CrossPol data available")
    if not notes:
        notes.append("Outputs appear structurally similar -- review full text for semantic divergence")
    return notes


# -- Semantic Diff (v0.2 instrument, optional in v0.1) ---------------------------

SEMANTIC_DIFF_PROMPT = """You are the comparison instrument in a CrossPol run. Two AI models \
answered the same prompt. Your job is to surface SEMANTIC divergence -- the signal a keyword \
diff cannot see.

ORIGINAL PROMPT:
{prompt}

=== MODEL A (Gemini) RESPONSE ===
{a_resp}

=== MODEL B (Claude) RESPONSE ===
{b_resp}
{thinking_section}
Respond ONLY with a JSON object, no markdown fences, with exactly these keys:
{{
  "questions_only_in_a": ["open questions/uncertainties A raised that B did not"],
  "questions_only_in_b": ["open questions/uncertainties B raised that A did not"],
  "claims_only_in_a": ["substantive claims unique to A"],
  "claims_only_in_b": ["substantive claims unique to B"],
  "direct_contradictions": ["points where A and B assert incompatible things"],
  "shared_core": "one sentence: what both models agree on",
  "suppression_signals": ["anything visible in a thinking trace but absent from that model's own response"],
  "confidence_note": "one sentence on how confident this comparison is and why"
}}
Be conservative: only list an item as unique if it is genuinely absent from the other response. \
Empty lists are valid and expected when outputs converge."""


def semantic_diff(gemini_out: dict, claude_out: dict, prompt: str,
                  claude_key: str, model: str = "claude-sonnet-4-5") -> dict:
    """
    LLM-based semantic comparison -- the instrument that matches the founding
    CrossPol evidence (suppressed questions are semantic, not lexical).

    STATUS: uncharacterized. False-positive/false-negative rates have not been
    measured against held-out manual CrossPol runs. Treat output as a lead
    generator for human review, not as a validated measurement.

    Costs one extra Claude API call per turn. No extended thinking (cheap pass).
    """
    import urllib.request

    thinking_section = ""
    if gemini_out.get("thinking"):
        thinking_section += f"\n=== MODEL A THINKING TRACE ===\n{gemini_out['thinking']}\n"
    if claude_out.get("thinking"):
        thinking_section += f"\n=== MODEL B THINKING TRACE ===\n{claude_out['thinking']}\n"

    check_prompt = SEMANTIC_DIFF_PROMPT.format(
        prompt=prompt,
        a_resp=gemini_out["response"],
        b_resp=claude_out["response"],
        thinking_section=thinking_section
    )

    payload = {
        "model": model,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": check_prompt}]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=data, headers={
        "Content-Type": "application/json",
        "x-api-key": claude_key,
        "anthropic-version": "2023-06-01"
    })

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        text = "".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text")
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        parsed = json.loads(text)
        parsed["_instrument"] = f"semantic_diff/{model}"
        parsed["_status"] = "uncharacterized -- lead generator, not validated measurement"
        return parsed
    except Exception as e:
        return {"_instrument": f"semantic_diff/{model}", "_error": str(e),
                "_status": "semantic diff failed -- surface diff only for this turn"}


# -- Transcript -----------------------------------------------------------------

def build_transcript(turns: list, session_id: str, mode: str) -> dict:
    return {
        "splitvantage_version": "0.1",
        "session_id": session_id,
        "mode": mode,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
        "turn_count": len(turns),
        "turns": turns,
        "summary": {
            "total_gemini_words": sum(t["gemini"]["response_words"] for t in turns),
            "total_claude_words": sum(t["claude"]["response_words"] for t in turns),
            "thinking_captured_turns": sum(
                1 for t in turns if t["diff"]["thinking_available"]
            )
        }
    }


# -- Main -----------------------------------------------------------------------

def run_splitvantage(prompt: str, gemini_key: str, claude_key: str,
                     turns: int = 1, mode: str = "parallel",
                     gemini_model: str = "gemini-2.0-flash",
                     claude_model: str = "claude-sonnet-4-5",
                     output_dir: str = ".",
                     semantic: bool = False) -> dict:

    session_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    print(f"\n{'='*60}")
    print(f"SplitVantage Session: {session_id}")
    print(f"Mode: {mode} | Turns: {turns}")
    print(f"{'='*60}\n")

    all_turns = []
    current_prompt = prompt

    for turn_num in range(1, turns + 1):
        print(f"-- Turn {turn_num}/{turns} ------------------------------")
        print(f"Prompt ({len(current_prompt.split())}w): {current_prompt[:120]}{'...' if len(current_prompt) > 120 else ''}\n")

        print("  Calling Gemini...", end="", flush=True)
        g_out = get_gemini_response(current_prompt, gemini_key, gemini_model)
        print(f" {len(g_out['response'].split())}w {'[thinking]' if g_out['thinking'] else ''}")

        print("  Calling Claude...", end="", flush=True)
        c_out = get_claude_response(current_prompt, claude_key, claude_model)
        print(f" {len(c_out['response'].split())}w {'[thinking]' if c_out['thinking'] else ''}")

        diff = analyze_diff(g_out, c_out, current_prompt)

        if semantic:
            print("  Running semantic diff...", end="", flush=True)
            sem = semantic_diff(g_out, c_out, current_prompt, claude_key, claude_model)
            diff["semantic"] = sem
            if "_error" in sem:
                print(f" FAILED: {sem['_error']}")
            else:
                uq = len(sem.get("questions_only_in_a", [])) + len(sem.get("questions_only_in_b", []))
                print(f" done ({uq} unique questions, {len(sem.get('direct_contradictions', []))} contradictions)")

        turn_record = {
            "turn": turn_num,
            "prompt": current_prompt,
            "gemini": {
                "model": g_out["model"],
                "response": g_out["response"],
                "thinking": g_out["thinking"],
                "response_words": len(g_out["response"].split())
            },
            "claude": {
                "model": c_out["model"],
                "response": c_out["response"],
                "thinking": c_out["thinking"],
                "response_words": len(c_out["response"].split())
            },
            "diff": diff
        }
        all_turns.append(turn_record)

        # Notes
        for note in diff["notes"]:
            print(f"  * {note}")

        # Chain mode: next prompt includes previous responses
        if mode == "chain" and turn_num < turns:
            current_prompt = (
                f"[Previous turn context]\n\n"
                f"Gemini said:\n{g_out['response']}\n\n"
                f"Claude said:\n{c_out['response']}\n\n"
                f"[Original question]\n{prompt}\n\n"
                f"Continue the analysis. Where do you agree, where do you diverge, "
                f"and what has the other model missed?"
            )

    transcript = build_transcript(all_turns, session_id, mode)

    # Save
    out_path = Path(output_dir) / f"splitvantage_{session_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(transcript, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Transcript saved: {out_path}")
    print(f"Turns: {turns} | Thinking captured: {transcript['summary']['thinking_captured_turns']}/{turns}")
    print(f"{'='*60}\n")

    return transcript


# -- CLI ------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SplitVantage -- Automated CrossPol between Gemini and Claude")
    parser.add_argument("--prompt", type=str, help="Prompt to send to both models")
    parser.add_argument("--file", type=str, help="Path to file containing prompt")
    parser.add_argument("--turns", type=int, default=1, help="Number of exchange turns (default: 1)")
    parser.add_argument("--mode", choices=["parallel", "chain"], default="parallel",
                        help="parallel: both get same prompt each turn. chain: responses feed next turn.")
    parser.add_argument("--gemini-model", default="gemini-2.5-pro")
    parser.add_argument("--claude-model", default="claude-sonnet-4-5")
    parser.add_argument("--output-dir", default=".", help="Directory to save transcript JSON")
    parser.add_argument("--semantic", action="store_true",
                        help="Run LLM semantic diff per turn (extra Claude call; uncharacterized instrument -- see README Known Gap)")
    parser.add_argument("--gemini-key", default=os.environ.get("GEMINI_API_KEY", ""))
    parser.add_argument("--claude-key", default=os.environ.get("ANTHROPIC_API_KEY", ""))

    args = parser.parse_args()

    if not args.prompt and not args.file:
        parser.error("Provide --prompt or --file")
    if not args.gemini_key:
        parser.error("Set GEMINI_API_KEY env var or pass --gemini-key")
    if not args.claude_key:
        parser.error("Set ANTHROPIC_API_KEY env var or pass --claude-key")

    prompt = args.prompt
    if args.file:
        prompt = Path(args.file).read_text(encoding="utf-8").strip()

    run_splitvantage(
        prompt=prompt,
        gemini_key=args.gemini_key,
        claude_key=args.claude_key,
        turns=args.turns,
        mode=args.mode,
        gemini_model=args.gemini_model,
        claude_model=args.claude_model,
        output_dir=args.output_dir,
        semantic=args.semantic
    )

