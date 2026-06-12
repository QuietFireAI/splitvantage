"""
run_test.py - SplitVantage founding run. Keys via env vars.
"""
import os, sys, json
sys.path.insert(0, r"C:\Users\Command Center\.gemini\antigravity\scratch\splitvantage")
from splitvantage import run_splitvantage

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
CLAUDE_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

if not GEMINI_KEY or not CLAUDE_KEY:
    print("ERROR: Set GEMINI_API_KEY and ANTHROPIC_API_KEY env vars before running.")
    sys.exit(1)

PROMPT = """An AI agent produces a response. Before delivering it, it is given one instruction:

Read what you just wrote as someone who has never heard of this project.
Does the first paragraph earn the reader before it explains?
Is there anything you assumed they knew that they don't?
Output PASS or identify the specific line that needs fixing.

Question: How likely is it that this single instruction -- added as a post-generation check
at 5-10 percent token overhead -- meaningfully improves response quality for a cold reader?
What are the failure modes of this approach? What would make it more robust?"""

OUTPUT_DIR = r"C:\Users\Command Center\.gemini\antigravity\scratch\splitvantage\transcripts"

result = run_splitvantage(
    prompt=PROMPT,
    gemini_key=GEMINI_KEY,
    claude_key=CLAUDE_KEY,
    turns=1,
    mode="parallel",
    output_dir=OUTPUT_DIR
)

t = result["turns"][0]

print("\n-- GEMINI RESPONSE --")
print(t["gemini"]["response"][:2000])
print("\n-- CLAUDE RESPONSE --")
print(t["claude"]["response"][:2000])
print("\n-- DIFF NOTES --")
for note in t["diff"]["notes"]:
    print(f"  * {note}")
print("\n-- GEMINI THINKING (first 600 chars) --")
print(t["gemini"]["thinking"][:600] or "(none captured)")
print("\n-- CLAUDE THINKING (first 600 chars) --")
print(t["claude"]["thinking"][:600] or "(none captured)")
