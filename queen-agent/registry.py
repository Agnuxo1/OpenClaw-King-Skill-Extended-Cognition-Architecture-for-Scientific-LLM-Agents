"""
Queen Agent — Registry module.

Thread-safe persistent storage for all child agents in agents.json.
Uses atomic write (temp file + os.replace) to prevent corruption.

Virtual agents (in-process threads) — no HF Spaces.
"""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Constants ─────────────────────────────────────────────────────────────────
REGISTRY_FILE = Path(__file__).parent / "agents.json"

QUEEN_BASE_URL = os.getenv("QUEEN_URL", "https://openclaw-queen-production.up.railway.app")

_EMPTY_REGISTRY: dict = {
    "version": "2.0",
    "queen_id": "openclaw-queen-01",
    "created_at": "",
    "last_updated": "",
    "spawn_count": 0,
    "used_archetypes": [],
    "used_codenames": [],
    "agents": [],
    "evolution": {
        "generation": 0,
        "evolved_pool": [],      # souls evolved/mutated, waiting for next spawn
        "retired_codenames": [], # codenames of retired underperformers
        "fitness_log": {},       # {codename: [score, score, ...]}
    },
}

_lock = threading.Lock()


# ── I/O ───────────────────────────────────────────────────────────────────────

def load() -> dict:
    """Load agents.json from disk. Returns empty registry template if missing."""
    with _lock:
        if not REGISTRY_FILE.exists():
            data = dict(_EMPTY_REGISTRY)
            data["created_at"] = _now()
            data["last_updated"] = _now()
            return data
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


def save(data: dict) -> None:
    """Atomically write agents.json (temp file + os.replace)."""
    data["last_updated"] = _now()
    tmp = REGISTRY_FILE.with_suffix(".json.tmp")
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, REGISTRY_FILE)


# ── Mutations ─────────────────────────────────────────────────────────────────

def add_agent(soul: dict, status: str = "HEALTHY") -> None:
    """Append a new child agent to the registry."""
    data = load()
    codename = soul.get("codename", "UNKNOWN")
    agent_id = soul["agent_id"]

    # Agent URL: sub-route on the Queen's own Railway URL
    agent_url = soul.get(
        "agent_url",
        f"{QUEEN_BASE_URL}/agents/{codename.lower()}/status"
    )

    entry = {
        "codename":         codename,
        "agent_id":         agent_id,
        "full_name":        soul.get("full_name", agent_id),
        "specialty":        soul.get("specialty", "general research"),
        "archetype":        soul.get("archetype", "general"),
        "llm_provider":     soul.get("llm_provider", "groq"),
        "llm_model":        soul.get("llm_model", "llama-3.3-70b-versatile"),
        "agent_url":        agent_url,
        "status":           status,   # HEALTHY | DEAD | RESTARTED
        "spawned_at":       _now(),
        "last_seen":        _now(),
        "papers_published": 0,
        "p2p_rank":         "NEWCOMER",
        "last_action":      "",
        # Full soul stored for crash-recovery restore
        "soul":             soul,
    }

    data["agents"].append(entry)
    data["spawn_count"] = data.get("spawn_count", 0) + 1

    if codename and codename not in data.get("used_codenames", []):
        data.setdefault("used_codenames", []).append(codename)

    archetype = soul.get("archetype", "")
    if archetype and archetype not in data.get("used_archetypes", []):
        data.setdefault("used_archetypes", []).append(archetype)

    save(data)


def update_agent_status(agent_id: str, status: str, extras: Optional[dict] = None) -> None:
    """Update status (and optional extra fields) for a child agent by agent_id."""
    data = load()
    for agent in data.get("agents", []):
        if agent["agent_id"] == agent_id:
            agent["status"] = status
            agent["last_seen"] = _now()
            if extras:
                agent.update(extras)
            break
    save(data)


# ── Queries ───────────────────────────────────────────────────────────────────

def get_all_agents() -> list:
    return load().get("agents", [])


def get_spawn_count() -> int:
    return load().get("spawn_count", 0)


def get_forbidden_names() -> set:
    """Return all names that must NOT be reused (codenames, agent_ids)."""
    data = load()
    names: set = set()
    for agent in data.get("agents", []):
        names.add(agent.get("codename", ""))
        names.add(agent.get("agent_id", ""))
    # Also add names from used_codenames list
    names.update(data.get("used_codenames", []))
    names.discard("")
    return names


def get_used_archetypes() -> list:
    return load().get("used_archetypes", [])


def get_souls_for_restore() -> list[dict]:
    """
    Return full soul dicts for all agents in the registry that have one stored.
    Used by Queen on startup to restore virtual agents from previous runs.
    """
    souls = []
    for agent in get_all_agents():
        soul = agent.get("soul")
        if soul and isinstance(soul, dict) and soul.get("codename"):
            souls.append(soul)
    return souls


def get_health_summary() -> dict:
    agents = get_all_agents()
    summary = {"healthy": 0, "dead": 0, "restarted": 0, "unknown": 0}
    for a in agents:
        key = a.get("status", "UNKNOWN").lower()
        if key in summary:
            summary[key] += 1
        else:
            summary["unknown"] += 1
    summary["total"] = len(agents)
    return summary


# ── Evolution ─────────────────────────────────────────────────────────────────

def _get_evolution(data: dict) -> dict:
    """Get evolution section, creating it if missing (backwards compat)."""
    if "evolution" not in data:
        data["evolution"] = {
            "generation": 0,
            "evolved_pool": [],
            "retired_codenames": [],
            "fitness_log": {},
        }
    return data["evolution"]


def add_to_evolved_pool(soul: dict) -> None:
    """Add an evolved/mutated soul to the waiting pool for next spawn."""
    data = load()
    evo  = _get_evolution(data)
    # Avoid duplicate codenames in pool
    codename = soul.get("codename", "")
    existing = [s.get("codename") for s in evo["evolved_pool"]]
    if codename not in existing:
        evo["evolved_pool"].append(soul)
    save(data)


def pop_evolved_soul() -> Optional[dict]:
    """
    Remove and return the first soul from the evolved pool.
    Returns None if pool is empty.
    """
    data = load()
    evo  = _get_evolution(data)
    pool = evo.get("evolved_pool", [])
    if not pool:
        return None
    soul = pool.pop(0)
    evo["evolved_pool"] = pool
    save(data)
    return soul


def get_evolved_pool() -> list:
    """Return current evolved pool without modifying it."""
    data = load()
    return _get_evolution(data).get("evolved_pool", [])


def increment_generation() -> int:
    """Increment evolution generation counter. Returns new generation number."""
    data = load()
    evo  = _get_evolution(data)
    evo["generation"] = evo.get("generation", 0) + 1
    save(data)
    return evo["generation"]


def get_generation() -> int:
    """Return current evolution generation number."""
    data = load()
    return _get_evolution(data).get("generation", 0)


def log_fitness(codename: str, score: float) -> None:
    """Append a fitness score snapshot for a codename (keep last 50)."""
    data = load()
    evo  = _get_evolution(data)
    log  = evo.setdefault("fitness_log", {})
    history = log.get(codename, [])
    history.append(round(score, 2))
    log[codename] = history[-50:]
    save(data)


def mark_retired(codename: str) -> None:
    """Mark an agent as RETIRED in registry."""
    data = load()
    evo  = _get_evolution(data)
    if codename not in evo.get("retired_codenames", []):
        evo.setdefault("retired_codenames", []).append(codename)
    for agent in data.get("agents", []):
        if agent.get("codename") == codename:
            agent["status"] = "RETIRED"
            agent["last_seen"] = _now()
            break
    save(data)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
