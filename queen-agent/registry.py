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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
