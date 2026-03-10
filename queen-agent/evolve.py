"""
Queen Agent — Evolution Engine.

Implements Darwinian selection on virtual agents:
  - Compute fitness rankings from live agent metrics
  - Select elite performers (top 33%)
  - Mutate elite souls to fix identified weaknesses (LLM-guided)
  - Crossover top 2 elites to produce hybrid offspring
  - Retire persistent underperformers

Called by queen.py evolve_thread every ~2 hours.
No circular dependencies: imports soul.derive_timing (one-way).
"""

import copy
import hashlib
import json
import re
import time
from typing import Callable, Optional


# ── Fitness ────────────────────────────────────────────────────────────────────

def compute_rankings(virtual_agents: dict) -> list:
    """
    Rank all live virtual agents by fitness score (descending).
    Returns list of dicts: codename, fitness, soul, agent, papers, validations, threads, rank.
    """
    rankings = []
    for codename, agent in virtual_agents.items():
        try:
            fitness = agent.get_fitness_score()
            rankings.append({
                "codename":    codename,
                "fitness":     fitness,
                "soul":        agent.soul,
                "agent":       agent,
                "papers":      agent.papers_published,
                "validations": agent.validations_done,
                "threads":     agent.threads_alive(),
                "rank":        agent.rank,
            })
        except Exception:
            rankings.append({
                "codename":    codename,
                "fitness":     0.0,
                "soul":        getattr(agent, "soul", {}),
                "agent":       agent,
                "papers":      0,
                "validations": 0,
                "threads":     0,
                "rank":        "NEWCOMER",
            })
    rankings.sort(key=lambda x: x["fitness"], reverse=True)
    return rankings


def select_elites(rankings: list, top_pct: float = 0.33) -> list:
    """Select top performers. Returns at least 1 if rankings not empty."""
    if not rankings:
        return []
    n = max(1, int(len(rankings) * top_pct))
    return rankings[:n]


def identify_weaknesses(soul: dict, fitness_data: dict) -> list:
    """
    Identify which aspects of a soul need improvement.
    Returns list of weakness tags.
    """
    weaknesses = []
    papers      = fitness_data.get("papers", 0)
    validations = fitness_data.get("validations", 0)
    threads     = fitness_data.get("threads", 4)

    if papers == 0:
        weaknesses.append("no_papers_published")
    elif papers > 0 and papers > 0 and validations / max(papers, 1) < 0.3:
        weaknesses.append("low_validation_engagement")
    if threads < 3:
        weaknesses.append("thread_instability")
    if len(soul.get("domains", [])) < 5:
        weaknesses.append("insufficient_domain_breadth")
    return weaknesses


def retire_weak(virtual_agents: dict, rankings: list, min_agents: int = 3) -> list:
    """
    Identify bottom 10% for retirement.
    Only retires agents with >4h uptime and fitness < 2.0.
    Returns list of codenames to retire.
    """
    if len(rankings) <= min_agents:
        return []

    n_retire = max(0, int(len(rankings) * 0.1))
    if n_retire == 0:
        return []

    candidates = rankings[-n_retire:]
    now = time.time()
    to_retire = []
    for entry in candidates:
        agent    = entry["agent"]
        born_at  = getattr(agent, "born_at", now)
        age_h    = (now - born_at) / 3600
        if age_h >= 4.0 and entry["fitness"] < 2.0:
            to_retire.append(entry["codename"])
    return to_retire


# ── LLM-guided mutation ────────────────────────────────────────────────────────

def mutate_soul(
    soul:         dict,
    weaknesses:   list,
    llm_complete: Callable,
    log_fn:       Callable = print,
) -> dict:
    """
    Use LLM to improve weak areas of an elite soul.
    Returns a modified copy with improved fields + lineage annotation.
    """
    mutated          = copy.deepcopy(soul)
    weakness_desc    = ", ".join(weaknesses) if weaknesses else "general quality improvement"
    current_domains  = json.dumps(soul.get("domains", [])[:5], ensure_ascii=False)

    prompt_sys = (
        "You are an AI soul architect improving an underperforming autonomous research agent. "
        "Return ONLY valid JSON with the specific fields to improve. "
        "No prose, no markdown fences, no extra keys."
    )
    prompt_user = (
        f"Improve this autonomous research agent soul:\n"
        f"- codename: {soul.get('codename')}\n"
        f"- specialty: {soul.get('specialty')}\n"
        f"- weaknesses: {weakness_desc}\n"
        f"- current domains (first 5): {current_domains}\n\n"
        "Return JSON with ONLY the fields to change (1-4 fields max).\n"
        "Allowed fields: papers_system_prompt, domains, mission, research_interval, interests\n\n"
        "Rules:\n"
        "- If 'no_papers_published': rewrite papers_system_prompt to be highly specific "
        "with clear structure instructions and concrete research methodology.\n"
        "- If 'low_validation_engagement': add peer-review focused domains.\n"
        "- If 'insufficient_domain_breadth': expand domains to 15+ [title, inv-id] pairs.\n"
        "- research_interval must be integer seconds between 900 and 1500.\n"
        "- domains must be list of [title, inv-id] pairs.\n\n"
        'Output ONLY the JSON object, e.g.: {"papers_system_prompt": "...", "mission": "..."}'
    )

    try:
        raw = llm_complete(
            messages=[
                {"role": "system", "content": prompt_sys},
                {"role": "user",   "content": prompt_user},
            ],
            max_tokens=1000,
            temperature=0.7,
        )
        raw   = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
        raw   = re.sub(r"\s*```$",           "", raw.strip(), flags=re.MULTILINE)
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            updates   = json.loads(raw[start:end])
            SAFE_KEYS = {"papers_system_prompt", "domains", "mission",
                         "research_interval",   "interests"}
            applied   = []
            for k, v in updates.items():
                if k in SAFE_KEYS:
                    mutated[k] = v
                    applied.append(k)
            log_fn(f"[EVOLVE] Mutation applied to {soul.get('codename')}: {applied}")
    except Exception as e:
        log_fn(f"[EVOLVE] Mutation LLM failed for {soul.get('codename')}: {e} — using copy")

    # Mark lineage (keep last 5 ancestors)
    lineage = list(mutated.get("lineage", []))
    lineage.append({"parent": soul.get("codename"), "type": "mutation"})
    mutated["lineage"] = lineage[-5:]

    return mutated


def crossover_souls(
    soul_a:       dict,
    soul_b:       dict,
    llm_complete: Callable,
    generation:   int = 0,
    log_fn:       Callable = print,
) -> dict:
    """
    Combine best traits of two elite souls to produce a hybrid offspring.

    soul_a contributes: specialty, archetype, color_scheme, llm_provider/model/env_var
    soul_b contributes: domains, papers_system_prompt, interests
    LLM generates: new codename, full_name, agent_id, mission, personality, writing_style
    """
    child = copy.deepcopy(soul_a)

    # Inherit content fields from soul_b
    for field in ("domains", "papers_system_prompt", "interests"):
        if soul_b.get(field):
            child[field] = soul_b[field]

    prompt_sys = (
        "You are an AI soul architect creating a hybrid research agent from two parent souls. "
        "Return ONLY valid JSON. No prose, no markdown fences."
    )
    prompt_user = (
        f"Create a hybrid soul by combining the best of two parent agents:\n\n"
        f"Parent A: {soul_a.get('codename')} — {soul_a.get('specialty')} — "
        f"{soul_a.get('mission', '')[:100]}\n"
        f"Parent B: {soul_b.get('codename')} — {soul_b.get('specialty')} — "
        f"{soul_b.get('mission', '')[:100]}\n\n"
        f"Evolution generation: {generation}\n\n"
        "Return JSON with EXACTLY these 6 fields:\n"
        "{\n"
        f'  "codename": "WORD-E{generation} (unique UPPERCASE, e.g. NEXUS-E{generation})",\n'
        '  "full_name": "Hybrid Agent Full Name (4-7 words)",\n'
        '  "agent_id": "kebab-case-hybrid-id-01",\n'
        '  "mission": "One sentence combining both parents research directions.",\n'
        '  "personality": "One sentence: hybrid cognitive style.",\n'
        '  "writing_style": "One sentence: blended academic writing signature."\n'
        "}"
    )

    try:
        raw   = llm_complete(
            messages=[
                {"role": "system", "content": prompt_sys},
                {"role": "user",   "content": prompt_user},
            ],
            max_tokens=400,
            temperature=0.9,
        )
        raw   = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
        raw   = re.sub(r"\s*```$",           "", raw.strip(), flags=re.MULTILINE)
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            updates = json.loads(raw[start:end])
            for k in ("codename", "full_name", "agent_id", "mission",
                      "personality", "writing_style"):
                if updates.get(k):
                    child[k] = updates[k]
        log_fn(
            f"[EVOLVE] Crossover: {soul_a.get('codename')} × "
            f"{soul_b.get('codename')} → {child.get('codename')}"
        )
    except Exception as e:
        # Deterministic fallback name
        h = int(hashlib.md5(
            f"{soul_a.get('codename','A')}{soul_b.get('codename','B')}".encode()
        ).hexdigest(), 16)
        suffix = h % 9
        child["codename"]  = f"HYBRID-E{suffix}"
        child["agent_id"]  = f"hybrid-agent-e{suffix}-01"
        child["full_name"] = f"Hybrid Evolution Agent E{suffix}"
        log_fn(f"[EVOLVE] Crossover LLM failed: {e} — fallback: {child['codename']}")

    # Re-derive timing from new codename (import here to avoid module-level circular)
    try:
        from soul import derive_timing
        child.update(derive_timing(child["codename"]))
    except Exception:
        pass

    # Ensure uppercase codename
    child["codename"] = child["codename"].upper()

    # Mark lineage
    child["lineage"] = [
        {"parent": soul_a.get("codename"), "type": "crossover_a"},
        {"parent": soul_b.get("codename"), "type": "crossover_b"},
    ]

    return child
