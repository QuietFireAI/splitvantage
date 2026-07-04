"""
Offline tests for splitvantage - no network, no API keys required.

These exercise the real comparison, notes, transcript, and orchestration logic
by faking the two model-call functions. The live cross-model run still needs
GEMINI_API_KEY + ANTHROPIC_API_KEY (see run_test.py); these tests do not, so the
tool's logic can be verified in CI or on any machine.

    pip install pytest && pytest -q
"""

import json
import sys
from pathlib import Path

# splitvantage.py lives at the repo root next to this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import splitvantage as sv


def _out(model, response, thinking=""):
    return {"model": model, "response": response, "thinking": thinking, "raw": {}}


# --- analyze_diff -----------------------------------------------------------

def test_analyze_diff_counts_uncertainty():
    g = _out("gemini/x", "This might be the case, perhaps, but it depends however.")
    c = _out("claude/y", "This is definitely the answer.")
    d = sv.analyze_diff(g, c, "the prompt here")
    assert d["gemini_uncertainty_signals"] >= 4
    assert d["claude_uncertainty_signals"] == 0
    assert d["uncertainty_delta"] == abs(
        d["gemini_uncertainty_signals"] - d["claude_uncertainty_signals"]
    )


def test_analyze_diff_lengths_and_prompt():
    g = _out("gemini/x", "one two three four five")
    c = _out("claude/y", "one two")
    d = sv.analyze_diff(g, c, "a b c")
    assert d["gemini_response_words"] == 5
    assert d["claude_response_words"] == 2
    assert d["length_delta_words"] == 3
    assert d["prompt_length_words"] == 3


def test_analyze_diff_thinking_flags():
    g = _out("gemini/x", "answer", thinking="some reasoning")
    c = _out("claude/y", "answer")
    d = sv.analyze_diff(g, c, "p")
    assert d["gemini_has_thinking"] is True
    assert d["claude_has_thinking"] is False
    assert d["thinking_available"] is True


# --- _generate_notes --------------------------------------------------------

def test_notes_length_divergence():
    notes = sv._generate_notes(0, 0, 300, 50, False, False)
    assert any("length divergence" in n.lower() for n in notes)


def test_notes_uncertainty_divergence():
    notes = sv._generate_notes(5, 1, 10, 10, False, False)
    assert any("uncertainty" in n.lower() for n in notes)


def test_notes_both_thinking_captured():
    notes = sv._generate_notes(0, 0, 10, 10, True, True)
    assert any("both" in n.lower() for n in notes)


def test_notes_similar_fallback():
    notes = sv._generate_notes(0, 0, 10, 11, False, False)
    assert any("structurally similar" in n.lower() for n in notes)


# --- build_transcript -------------------------------------------------------

def test_build_transcript_structure_and_summary():
    turns = [{
        "turn": 1, "prompt": "p",
        "gemini": {"model": "g", "response": "a b c", "thinking": "", "response_words": 3},
        "claude": {"model": "c", "response": "a b", "thinking": "", "response_words": 2},
        "diff": {"thinking_available": True},
    }]
    t = sv.build_transcript(turns, "sess1", "parallel")
    assert t["splitvantage_version"] == "0.1"
    assert t["session_id"] == "sess1"
    assert t["turn_count"] == 1
    assert t["summary"]["total_gemini_words"] == 3
    assert t["summary"]["total_claude_words"] == 2
    assert t["summary"]["thinking_captured_turns"] == 1


# --- run_splitvantage (full orchestration, faked network) -------------------

def test_run_splitvantage_parallel(monkeypatch, tmp_path):
    calls = {"g": 0, "c": 0}

    def fake_g(prompt, key, model="gemini-2.0-flash"):
        calls["g"] += 1
        return _out(f"gemini/{model}", "gemini answer maybe perhaps", thinking="g-think")

    def fake_c(prompt, key, model="claude-sonnet-4-5"):
        calls["c"] += 1
        return _out(f"claude/{model}", "claude is certain here", thinking="c-think")

    monkeypatch.setattr(sv, "get_gemini_response", fake_g)
    monkeypatch.setattr(sv, "get_claude_response", fake_c)

    tr = sv.run_splitvantage("question?", "gk", "ck", turns=2,
                             mode="parallel", output_dir=str(tmp_path))
    assert tr["turn_count"] == 2
    assert calls == {"g": 2, "c": 2}
    files = list(Path(tmp_path).glob("splitvantage_*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["turns"][0]["gemini"]["response"].startswith("gemini")
    assert data["summary"]["thinking_captured_turns"] == 2


def test_run_splitvantage_chain_threads_context(monkeypatch, tmp_path):
    seen_prompts = []

    def fake_g(prompt, key, model="gemini-2.0-flash"):
        seen_prompts.append(prompt)
        return _out("gemini/x", "g resp")

    def fake_c(prompt, key, model="claude-sonnet-4-5"):
        return _out("claude/y", "c resp")

    monkeypatch.setattr(sv, "get_gemini_response", fake_g)
    monkeypatch.setattr(sv, "get_claude_response", fake_c)

    sv.run_splitvantage("orig question", "gk", "ck", turns=2,
                        mode="chain", output_dir=str(tmp_path))
    assert len(seen_prompts) == 2
    # turn 1 sees the raw prompt; turn 2 sees threaded context
    assert seen_prompts[0] == "orig question"
    assert "Previous turn context" in seen_prompts[1]
    assert "orig question" in seen_prompts[1]


# --- semantic diff prompt construction (no API call) ------------------------

def test_semantic_diff_prompt_builds():
    p = sv.SEMANTIC_DIFF_PROMPT.format(
        prompt="P", a_resp="A", b_resp="B", thinking_section=""
    )
    assert "MODEL A (Gemini)" in p
    assert "MODEL B (Claude)" in p
    assert "JSON object" in p


def test_uncertainty_words_need_word_boundaries():
    # regression: substring hits ("might" in "almighty"/"mighty") scored as
    # hedging. Confirmed live 07/2026; word-boundary counting is the fix.
    from splitvantage import analyze_diff
    g = _out("g", "The almighty and mighty kingdom highlights certainty.")
    c = _out("c", "It might possibly work, though this is unclear.")
    d = analyze_diff(g, c, "x")
    assert d["gemini_uncertainty_signals"] == 0
    assert d["claude_uncertainty_signals"] == 3
