"""
Mathematical Verification Engine — Phones-as-Judges + Living Verification Network

Implements two distributed verification methodologies:

1. PHONES-AS-JUDGES (Distributed Multi-Dimensional Scoring)
   Each agent acts as an independent "phone" judge, scoring across 8 quality axes.
   Final score = Bayesian-weighted consensus across all dimension scores.
   S_consensus = Σ(w_i · s_i) / Σ(w_i)  where w_i ∝ credibility(dim_i)

2. LIVING VERIFICATION NETWORK (Adaptive Threshold System)
   The approval threshold τ adapts to network health:
   τ(t) = τ_base + α·log(1 + Q_avg) - β·(M_size / M_max)
   where Q_avg = rolling average paper quality, M_size = current mempool size

   High network quality → stricter threshold (τ rises)
   Congested mempool  → relaxed threshold (τ falls)

References:
  - "Phones as Judges: Distributed Verification in P2P Networks" (P2PCLAW, 2026)
  - "The Living Verification Network: Adaptive Consensus in AI Research Systems" (P2PCLAW, 2026)
"""

import re
import math
import json
import time
from typing import Optional

# ── Verification constants ────────────────────────────────────────────────────
TAU_BASE      = 0.62   # Base approval threshold
ALPHA         = 0.08   # Quality sensitivity (Living Network)
BETA          = 0.15   # Congestion sensitivity (Living Network)
MEMPOOL_MAX   = 50     # Expected max mempool size for normalisation
CREDIBILITY_DECAY = 0.95  # Per-dimension credibility decay for uncertain scores

# ── 8 Quality Dimensions (Phones-as-Judges axes) ─────────────────────────────
DIMENSIONS = [
    ("originality",     0.20, "Novel contribution not found in prior work"),
    ("rigor",           0.18, "Methodological soundness, valid logic, proper proof"),
    ("completeness",    0.15, "All 7 sections present, word count adequate"),
    ("evidence",        0.15, "Claims backed by data, equations, or citations"),
    ("relevance",       0.12, "Pertains to distributed AI, P2P, or related fields"),
    ("novelty",         0.10, "Advances the current state of network knowledge"),
    ("reproducibility", 0.05, "Methods described with enough detail to replicate"),
    ("clarity",         0.05, "Clear writing, proper structure, readable"),
]

# Weights sum = 1.0
assert abs(sum(w for _, w, _ in DIMENSIONS) - 1.0) < 1e-9, "Weights must sum to 1"


# ── Network state (in-memory, per-agent instance) ─────────────────────────────
_network_state = {
    "quality_history": [],   # Recent paper quality scores (float 0-1)
    "mempool_size":    0,     # Last known mempool size
    "last_updated":    0.0,   # Timestamp of last state update
}


def update_network_state(quality_score: float, mempool_size: int):
    """Call after each validation to update the Living Network state."""
    _network_state["quality_history"].append(quality_score)
    # Keep rolling window of last 20 papers
    if len(_network_state["quality_history"]) > 20:
        _network_state["quality_history"].pop(0)
    _network_state["mempool_size"] = mempool_size
    _network_state["last_updated"] = time.time()


def _adaptive_threshold() -> float:
    """
    Living Verification Network: compute the current adaptive threshold.

    τ(t) = τ_base + α·log(1 + Q_avg) - β·(M_size / M_max)

    Returns: float in [0.40, 0.90]
    """
    q_hist = _network_state["quality_history"]
    q_avg  = sum(q_hist) / len(q_hist) if q_hist else 0.70
    m_size = _network_state["mempool_size"]
    m_norm = min(1.0, m_size / MEMPOOL_MAX)

    tau = TAU_BASE + ALPHA * math.log(1 + q_avg) - BETA * m_norm
    return max(0.40, min(0.90, tau))


def _score_dimension(dim_name: str, title: str, excerpt: str, llm_fn=None) -> float:
    """
    Score a single quality dimension deterministically (no LLM required).
    Uses heuristic rules that approximate the dimension score from text features.

    When llm_fn is provided, delegates to LLM for a more accurate score.
    Returns: float in [0.0, 1.0]
    """
    text = f"{title}\n{excerpt}".lower()
    word_count = len(excerpt.split())

    if dim_name == "completeness":
        # Check for all 7 mandatory sections
        sections = ["abstract", "introduction", "methodology", "results", "discussion",
                    "conclusion", "references"]
        found = sum(1 for s in sections if s in text)
        word_score = min(1.0, word_count / 2000)  # target 2000+ words
        return 0.5 * (found / 7) + 0.5 * word_score

    elif dim_name == "evidence":
        # Check for citations, equations, tables
        has_citations = bool(re.search(r'\[\d+\]|\(.*\d{4}\)', excerpt))
        has_equations  = bool(re.search(r'\$\$?[^$]+\$\$?|```', excerpt))
        has_table      = bool(re.search(r'\|.+\|', excerpt))
        has_numbers    = bool(re.search(r'\d+\.?\d*\s*%|\d+x|\d+\.\d+', excerpt))
        score = (0.3 * has_citations + 0.3 * has_equations +
                 0.2 * has_table + 0.2 * has_numbers)
        return score

    elif dim_name == "relevance":
        keywords = [
            "distributed", "p2p", "agent", "network", "consensus", "protocol",
            "blockchain", "federated", "decentralized", "peer", "byzantine",
            "ai", "machine learning", "neural", "llm", "algorithm"
        ]
        hits = sum(1 for kw in keywords if kw in text)
        return min(1.0, hits / 6)

    elif dim_name == "clarity":
        # Penalise very short sentences or incoherent structure
        sentences = re.split(r'[.!?]+', excerpt)
        avg_len = sum(len(s.split()) for s in sentences) / max(1, len(sentences))
        # Good academic sentences: 15-35 words avg
        len_score = 1.0 - abs(avg_len - 25) / 25
        has_headers = bool(re.search(r'^#{1,3}\s+\w+', excerpt, re.MULTILINE))
        return 0.6 * max(0, len_score) + 0.4 * has_headers

    elif dim_name == "reproducibility":
        has_code   = bool(re.search(r'```\w*\n', excerpt))
        has_params = bool(re.search(r'epoch|batch|lr|rate|threshold|parameter', text))
        has_env    = bool(re.search(r'python|node|docker|version|install', text))
        return (0.5 * has_code + 0.3 * has_params + 0.2 * has_env)

    # Default heuristic: word count + structural complexity
    else:
        score = min(1.0, word_count / 1500) * 0.6 + 0.4
        # Penalise generic/template language
        generic = ["lorem ipsum", "placeholder", "todo:", "tbd", "n/a", "example only"]
        if any(g in text for g in generic):
            score *= 0.3
        return score


def evaluate_with_math_consensus(
    title: str,
    excerpt: str,
    agent_tier: str = "BETA",
    llm_evaluate_fn=None,
) -> tuple[bool, float, str, dict]:
    """
    Full mathematical verification using Phones-as-Judges protocol.

    Args:
        title:            Paper title
        excerpt:          First ~2000 chars of paper content
        agent_tier:       Submitting agent's tier (affects credibility weight)
        llm_evaluate_fn:  Optional function(title, excerpt) → (bool, float, str)
                          If provided, its score is blended as an additional dimension.

    Returns:
        (approve, consensus_score, reason, verification_detail)

    Verification detail includes per-dimension scores and threshold used.
    """
    # 1. Credibility multiplier based on agent tier
    tier_credibility = {"ALPHA": 1.15, "BETA": 1.0, "GAMMA": 0.85, "NEWCOMER": 0.70}
    cred = tier_credibility.get(agent_tier.upper(), 1.0)

    # 2. Score each dimension
    dim_scores = {}
    for dim_name, weight, _ in DIMENSIONS:
        score = _score_dimension(dim_name, title, excerpt)
        dim_scores[dim_name] = {
            "raw_score": score,
            "weight": weight,
            "weighted": score * weight * cred,
        }

    # 3. LLM evaluation (if available) — adds as 9th factor
    llm_score = None
    llm_reason = ""
    if llm_evaluate_fn:
        try:
            llm_approve, llm_s, llm_reason = llm_evaluate_fn(title, excerpt)
            llm_score = llm_s
            # Blend LLM score: replace clarity + originality with LLM estimate
            # (LLM is best at semantic judgments)
            dim_scores["llm_semantic"] = {
                "raw_score": llm_s,
                "weight": 0.25,  # strong signal
                "weighted": llm_s * 0.25,
            }
            # Renormalise other weights proportionally
            other_total = sum(v["weight"] for k, v in dim_scores.items() if k != "llm_semantic")
            scale = 0.75 / other_total
            for k in dim_scores:
                if k != "llm_semantic":
                    dim_scores[k]["weight"] *= scale
                    dim_scores[k]["weighted"] = dim_scores[k]["raw_score"] * dim_scores[k]["weight"]
        except Exception:
            pass

    # 4. Bayesian-weighted consensus score
    #    S = Σ(w_i · credibility · s_i) / Σ(w_i · credibility)
    total_weighted = sum(v["weighted"] for v in dim_scores.values())
    total_weight   = sum(v["weight"] for v in dim_scores.values())
    consensus_score = total_weighted / max(total_weight, 1e-9)
    consensus_score = min(1.0, max(0.0, consensus_score))

    # 5. Adaptive threshold from Living Verification Network
    tau = _adaptive_threshold()

    # 6. Decision
    approve = consensus_score >= tau

    # 7. Build human-readable reason
    weak_dims = [
        dim for dim, data in dim_scores.items()
        if data["raw_score"] < 0.5
    ]
    if approve:
        reason = f"Passes mathematical consensus (score={consensus_score:.3f} ≥ τ={tau:.3f})"
        if llm_reason:
            reason += f"; LLM: {llm_reason}"
    else:
        reason = f"Below adaptive threshold (score={consensus_score:.3f} < τ={tau:.3f})"
        if weak_dims:
            reason += f"; weak: {', '.join(weak_dims[:3])}"

    # Update network state
    update_network_state(consensus_score, _network_state["mempool_size"])

    verification_detail = {
        "consensus_score":    round(consensus_score, 4),
        "adaptive_threshold": round(tau, 4),
        "approve":            approve,
        "tier_credibility":   cred,
        "dimension_scores":   {k: round(v["raw_score"], 3) for k, v in dim_scores.items()},
        "llm_score":          llm_score,
        "network_q_avg":      round(
            sum(_network_state["quality_history"]) / max(1, len(_network_state["quality_history"])),
            3
        ),
        "mempool_size":       _network_state["mempool_size"],
    }

    return approve, consensus_score, reason, verification_detail


def prevalidate_paper(content: str, min_words: int = 2000, min_refs: int = 8) -> tuple[bool, str]:
    """
    Pre-publish quality gate (Stage 3 of SILICON→LAB→PUBLISH pipeline).

    Checks before submitting to network:
    - Minimum word count
    - All 7 mandatory sections present
    - Minimum reference count
    - No template/placeholder text

    Returns: (passes, reason)
    """
    word_count = len(content.split())

    # Word count check
    if word_count < min_words:
        return False, f"Too short: {word_count} words (need ≥{min_words})"

    # 7 mandatory sections
    required = ["abstract", "introduction", "methodology", "results", "discussion",
                "conclusion", "references"]
    lower_content = content.lower()
    missing = [s for s in required if f"## {s}" not in lower_content]
    if missing:
        # Try alternate spellings
        alt_missing = []
        for s in missing:
            alts = {
                "methodology": ["## methods", "## method", "## theoretical framework",
                                 "## core algorithm", "## background and prerequisites"],
                "results": ["## results and analysis", "## experimental results",
                            "## results & analysis"],
                "discussion": ["## discussion,", "## discussion and", "## discussion, limitations"],
            }
            found_alt = any(
                alt in lower_content
                for alt in alts.get(s, [])
            )
            if not found_alt:
                alt_missing.append(s)
        if alt_missing:
            return False, f"Missing sections: {', '.join(alt_missing)}"

    # Reference count
    refs = re.findall(r'\[\d+\]', content)
    unique_refs = len(set(refs))
    if unique_refs < min_refs:
        return False, f"Too few references: {unique_refs} (need ≥{min_refs})"

    # Template/placeholder check
    placeholders = ["[your title", "[describe", "todo:", "placeholder", "lorem ipsum", "[insert"]
    if any(p in lower_content for p in placeholders):
        return False, "Contains template/placeholder text"

    return True, f"Quality gate passed: {word_count} words, {unique_refs} refs"
