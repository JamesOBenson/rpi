#!/usr/bin/env python3
"""LLM micro-bench: prefill vs generation, by prompt size."""
import os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from llm_engine import LocalLLM

SHORT_PROMPT = (
    "You are STEM Buddy, a friendly AI for 4th-5th graders.\n"
    "Answer in 1-2 short sentences, simple words, no labels.\n"
    "Use the facts below when relevant; ignore them otherwise."
)

FACTS = [
    {"text": "The sky is blue because sunlight scatters off air molecules. Blue light scatters more than red light, so the whole sky looks blue to our eyes."},
    {"text": "Octopuses have blue blood because they use hemocyanin, which contains copper, instead of the iron in our blood."},
    {"text": "Blue light has a shorter wavelength than red light, so it scatters in all directions when sunlight hits the atmosphere."},
]

llm = LocalLLM(n_threads=4)
llm.initialize()

def measure(prompt, max_tokens):
    t0 = time.time()
    llm.llama(prompt, max_tokens=max_tokens, temperature=0.3)
    return time.time() - t0

q = "why is the sky blue"
variants = {"FULL+3facts (current)": llm._build_prompt(q, FACTS)}
for n, name in [(3, "SHORT+3facts"), (2, "SHORT+2facts"), (1, "SHORT+1fact")]:
    ctx_text = "\n".join("- " + c["text"] for c in FACTS[:n])
    user_msg = ("Relevant facts:\n%s\n\nQuestion: %s\n\n"
                "Give a short, kid-friendly answer (1-2 sentences)." % (ctx_text, q))
    variants[name] = (
        "

llm = LocalLLM(n_threads=4)
llm.initialize()

def measure(prompt, max_tokens):
    t0 = time.time()
    llm.llama(prompt, max_tokens=max_tokens, temperature=0.3)
    return time.time() - t0

q = "why is the sky blue"
variants = {"FULL+3facts (current)": llm._build_prompt(q, FACTS)}
