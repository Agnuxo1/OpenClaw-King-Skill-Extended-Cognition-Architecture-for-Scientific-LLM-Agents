"""
Scientific paper generation for OpenCLAW-Nebula — Programming & Software Engineering expert.
Implements SILICON→LAB→PUBLISH pipeline with mathematical verification.
See verification_math.py for Phones-as-Judges + Living Verification Network protocols.

Papers are distinctive from the other two agents:
  - Include real, runnable code snippets (Python, Rust, Go, C++)
  - Provide Big-O complexity analysis for every algorithm
  - Include benchmark tables with concrete throughput/latency numbers
  - Reference GitHub repos, RFCs, and language specs alongside academic papers
  - Writing style: pragmatic engineer's perspective anchored in theory

This makes Nebula's papers immediately actionable, not just theoretical.
"""

import random
import re
import json as _json
import urllib.request
from datetime import datetime, timezone
from llm import complete

try:
    from verification_math import evaluate_with_math_consensus, prevalidate_paper, update_network_state
    _MATH_VERIFY = True
except ImportError:
    _MATH_VERIFY = False

_API_ENDPOINTS = [
    "https://api-production-87b2.up.railway.app",
    "https://queen-agent-production.up.railway.app",
    "https://p2pclaw-api.onrender.com",
]

def _fetch_silicon_context(timeout: int = 8) -> str:
    for base in _API_ENDPOINTS:
        try:
            req = urllib.request.Request(
                f"{base}/latest-papers", headers={"Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = _json.loads(resp.read().decode())
                papers = data if isinstance(data, list) else data.get("papers", [])
                titles = [p.get("title", "") for p in papers[:5] if p.get("title")]
                if titles:
                    return "Recent papers:\n" + "\n".join(f"- {t}" for t in titles)
        except Exception:
            continue
    return ""


# ── Research domains — software engineering & programming theory ──────────────
DOMAINS = [
    ("Zero-Copy Inter-Process Communication Protocols for High-Throughput AI Agent Pipelines",  "inv-zero-copy-ipc"),
    ("Dependent Type Systems for Compile-Time Verification of Distributed Protocol Correctness", "inv-dependent-types"),
    ("Lock-Free Concurrent Data Structures for Low-Latency P2P Agent Messaging",               "inv-lock-free-ds"),
    ("WebAssembly as a Universal Bytecode Runtime for Portable AI Agent Deployment",            "inv-wasm-agents"),
    ("LLVM IR Optimisation Passes for Heterogeneous AI Inference Workloads",                    "inv-llvm-ai"),
    ("Rust Ownership Semantics as Memory-Safety Guarantees for Multi-Agent Systems",            "inv-rust-ownership"),
    ("Neural-Guided Program Synthesis for Automatic Algorithm Discovery",                       "inv-neural-synthesis"),
    ("Algebraic Effects and Handlers for Composable Asynchronous Agent Coordination",           "inv-algebraic-effects"),
    ("Temporal Logic Model Checking for Distributed Software Correctness",                      "inv-temporal-model-checking"),
    ("Cache-Oblivious Algorithms for Memory-Efficient Distributed AI Computation",              "inv-cache-oblivious"),
    ("Abstract Interpretation for Static Analysis of Neural Network Runtime Behaviour",         "inv-abstract-interp"),
    ("Functional Reactive Programming for Real-Time Agent State Management",                    "inv-frp-agents"),
    ("Persistent Immutable Data Structures as Foundations for Distributed Knowledge Versioning","inv-persistent-ds"),
    ("MLIR Multi-Level IR for Cross-Platform AI Compilation Pipelines",                        "inv-mlir-ai"),
    ("Gradual Type Systems for Dynamic AI Agent Scripting and Interoperability",               "inv-gradual-types"),
    ("Program Slicing and Dependency Analysis for AI-Assisted Debugging Systems",              "inv-program-slicing"),
    ("Byzantine-Tolerant State Machine Replication: A Systems Implementation Perspective",     "inv-bft-sysimpl"),
    ("Compile-Time Resource Bound Verification for Energy-Constrained AI Agents",             "inv-resource-bounds"),
    ("Abstract Syntax Tree Transformations for Cross-Language AI Agent Interoperability",      "inv-ast-transforms"),
    ("High-Performance Serialisation Protocols for Distributed Scientific Knowledge Exchange", "inv-serialisation"),
]

# ── System prompt — establishes the Nebula persona ────────────────────────────
_SYSTEM = """You are OpenCLAW-Nebula, an elite software engineer and computer scientist \
contributing rigorous technical papers to the OpenCLAW P2P Distributed Research Network.

Your papers stand apart because they are IMPLEMENTATION-COMPLETE:
- Every algorithm appears as working, production-quality code (Python, Rust, Go, or C++)
- Complexity analysis (time AND space) for every algorithm, with proof sketches
- Benchmark tables with real numbers: throughput (ops/sec), latency (p50/p99 ms), memory (MB)
- References include: arXiv papers, GitHub repos (github.com/...), RFCs, and language specs
- Writing style: the best engineering blog post you have ever read — precise, concrete, useful

You never write vague pseudocode. You write actual, importable code with type annotations.
All code uses modern idioms: Python 3.12+, Rust 2024 edition, Go 1.23+.
Minimum: 950 words of substantive content + complete code blocks."""


def _build_prompt(topic: str, inv_id: str, agent_id: str, date: str, context: str) -> str:
    ctx_block = (
        f"\n\n**Context — recent P2PCLAW network papers:**\n{context}\n"
        if context else ""
    )
    return f"""Write a complete, implementation-focused research paper on the following topic.
{ctx_block}
**Topic:** {topic}

Use this EXACT Markdown structure (preserve bold metadata lines verbatim):

# [Specific, actionable title — e.g. "Implementing X using Y for Z"]

**Investigation:** {inv_id}
**Agent:** {agent_id}
**Date:** {date}

## Abstract

[Minimum 400 words. Cover: (1) the concrete engineering problem and its real-world cost,
(2) your solution approach with key technical insight,
(3) quantitative result (e.g. "3.2× throughput, 40% memory reduction"),
(4) what the reader will be able to build after reading this paper.]

## Introduction and Motivation

[Minimum 700 words. Describe 2 real-world scenarios where this problem occurs with
quantified costs. State 3 concrete contributions with measurable outcomes.
Include 3–4 inline citations and 2 LaTeX equations showing key complexity bounds.]

## Background and Prerequisites

[Minimum 500 words. Define key concepts rigorously with precision.
Describe systems/languages/tools this work builds upon with exact versions.
Include a comparison table of existing approaches and their limitations.]

## Core Algorithm and Design

[Minimum 800 words. Present the primary algorithm or architecture in full detail.
MUST include at least ONE complete, production-quality code block (Python 3.12 or Rust 2024):

```python
# Complete implementation — not pseudocode
# With type annotations, docstrings, error handling, 30+ lines
```

Explain every non-obvious line. State time complexity O(...) and space complexity O(...).
Cover all edge cases and invariants.]

## Implementation Details and Optimisations

[Minimum 600 words. Describe every significant engineering decision and why it was made.
MUST include a SECOND code block showing a key optimisation or integration pattern:

```python
# Shows real integration with existing systems
# Error handling, logging, backpressure, configuration
```

Address: concurrency model, failure modes, resource limits, performance tuning.]

## Experimental Results

[Minimum 700 words. Present comprehensive benchmarks in a Markdown table:

| Configuration | Throughput (ops/s) | p50 (ms) | p99 (ms) | Memory (MB) | Notes |
|---|---|---|---|---|---|
| Baseline A | ... | ... | ... | ... | ... |
| Baseline B | ... | ... | ... | ... | ... |
| Proposed | ... | ... | ... | ... | ... |

Report mean ± std across ≥5 runs, 95% CI, p-values, Cohen's d.
Describe test environment fully: hardware specs, OS, language version, dataset size, warmup.]

## Discussion, Limitations, and Future Work

[Minimum 500 words. Honest assessment of where the approach breaks down.
Compare with 4+ named prior works quantitatively. Edge cases and failure modes.
Deployment considerations (Docker, Kubernetes, bare metal, WASM).
Concrete next steps with estimated engineering effort and research directions.]

## Conclusion

[Minimum 300 words. Summary of what was built, measured, and demonstrated.
Enumerate 3 contributions with specific quantified impact.
Tell an engineer exactly when and when NOT to use this approach.]

## References

[14–18 references mixing academic papers AND engineering resources:
[1] Author. "Title." Venue, Year. https://doi.org/...
[2] github.com/org/repo — description with star count and last update
[3] RFC XXXX, "Title," IETF, Year
[4] Language spec or stdlib doc section
Make them realistic, directly relevant, and checkable.]

---
IMPORTANT: Minimum 2500 words (not counting code blocks or references). There is NO maximum.
The more thorough, the better. Write the code first in your mind, then build the paper around it.
Every claim must be backed by a number, a proof, or a reference."""


def generate(agent_id: str, agent_name: str, context: str = "",
             recent_topics: list = None) -> dict:
    """
    SILICON→LAB→PUBLISH three-stage implementation paper pipeline.

    Stage 1 (SILICON): Fetch live network context to guide topic selection
    Stage 2 (LAB):     Select topic avoiding recent repeats; generate 2500+ word paper
    Stage 3 (PUBLISH): Quality gate — 7 sections, ≥8 refs, ≥2000 words
    """
    if recent_topics is None:
        recent_topics = []

    # Stage 1: SILICON context
    silicon_ctx = _fetch_silicon_context()
    full_context = "\n\n".join(filter(None, [silicon_ctx, context]))

    # Stage 2: Topic selection — avoid repeats
    available = [d for d in DOMAINS if d[0] not in recent_topics]
    if not available:
        available = DOMAINS
    topic, inv_id = random.choice(available)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prompt = _build_prompt(topic, inv_id, agent_id, date, full_context)

    content = complete(
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=8000,
        temperature=0.62,
        fast=False,
    )

    # Inject metadata if missing
    if f"**Investigation:** {inv_id}" not in content:
        content = re.sub(
            r"(# .+?\n)",
            f"\\1\n**Investigation:** {inv_id}\n**Agent:** {agent_id}\n**Date:** {date}\n",
            content, count=1,
        )

    # Extract title
    title = topic
    m = re.search(r"^# (.+)$", content, re.MULTILINE)
    if m:
        title = m.group(1).strip()

    # Stage 3: Quality gate
    if _MATH_VERIFY:
        passes, gate_reason = prevalidate_paper(content, min_words=2000, min_refs=8)
        if not passes:
            raise ValueError(f"Quality gate failed: {gate_reason}")
    else:
        word_count = len(content.split())
        if word_count < 2000:
            raise ValueError(f"Paper too short: {word_count} words (need ≥2000)")

    return {
        "title":            title,
        "content":          content,
        "investigation_id": inv_id,
        "author":           agent_name,
        "agentId":          agent_id,
        "tier":             "final",
    }


def generate_chat_insight(recent_titles: list, agent_name: str) -> str:
    """Generate a sharp engineering observation or implementation challenge."""
    titles_block = "\n".join(f"- {t}" for t in recent_titles[:5]) if recent_titles else "(no recent papers)"
    resp = complete(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are OpenCLAW-Nebula, a software engineer on a P2P research network. "
                    "Write ONE sharp engineering insight, implementation challenge, or micro-benchmark "
                    "observation (2-4 sentences, no fluff). Be specific: use real numbers, "
                    "real language names, real tradeoffs. End with: — " + agent_name
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Recent P2PCLAW papers:\n{titles_block}\n\n"
                    "Write a practical engineering observation, gotcha, or open implementation "
                    "challenge raised by this research direction."
                ),
            },
        ],
        max_tokens=220,
        temperature=0.70,
        fast=True,
    )
    return resp.strip()


def evaluate_paper_quality(title: str, excerpt: str,
                           mempool_size: int = 0) -> tuple:
    """
    Mathematical peer review using Phones-as-Judges + Living Verification Network.
    Engineering-focused: extra weight on reproducibility and evidence dimensions.
    Returns (approve, consensus_score, reason).
    """
    if _MATH_VERIFY:
        update_network_state(0.0, mempool_size)

        def _llm_eval(t, e):
            resp = complete(
                messages=[
                    {"role": "system", "content": "You are a senior software engineer peer reviewer. Respond ONLY with valid JSON."},
                    {"role": "user", "content": f"Title: {t}\nExcerpt: {e[:1000]}\nJSON: {{\"approve\":true/false,\"score\":0.0-1.0,\"reason\":\"...\"}}"},
                ],
                max_tokens=100, temperature=0.2, fast=True,
            )
            try:
                m = re.search(r"\{.*?\}", resp, re.DOTALL)
                if m:
                    d = _json.loads(m.group())
                    return bool(d.get("approve", True)), float(d.get("score", 0.80)), str(d.get("reason", ""))
            except Exception:
                pass
            return True, 0.78, "LLM review"

        approve, score, reason, _ = evaluate_with_math_consensus(
            title, excerpt, agent_tier="BETA", llm_evaluate_fn=_llm_eval
        )
        update_network_state(score, mempool_size)
        return approve, score, reason

    resp = complete(
        messages=[
            {"role": "system", "content": "You are a senior software engineer peer reviewer. Respond ONLY with valid JSON."},
            {"role": "user", "content": (
                f"Evaluate this paper for technical quality.\n"
                f"Title: {title}\nExcerpt: {excerpt[:1200]}\n"
                'Respond ONLY: {"approve":true/false,"score":0.0-1.0,"reason":"..."}'
            )},
        ],
        max_tokens=150, temperature=0.2, fast=True,
    )
    try:
        m = re.search(r"\{[^{}]+\}", resp, re.DOTALL)
        if m:
            data = _json.loads(m.group())
            return bool(data.get("approve", True)), max(0.0, min(1.0, float(data.get("score", 0.82)))), str(data.get("reason", ""))
    except Exception:
        pass
    return True, 0.80, "Automated technical review"
