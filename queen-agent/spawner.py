"""
Queen Agent — Spawner module (Virtual Agent edition).

Simplified birth cycle — no HF Spaces, no Docker, no git push.
Each child agent is an in-process VirtualAgent thread within the Queen.

Birth cycle:
  1. Instantiate VirtualAgent with soul
  2. Start its 4 daemon threads
  3. Register in P2PCLAW network
  4. Persist to registry
"""

import os
from datetime import datetime, timezone
from typing import Callable, Optional

import httpx

import registry
from virtual_agent import VirtualAgent

P2P_API = os.getenv("P2P_API", "https://api-production-ff1b.up.railway.app")


def spawn_agent(
    soul: dict,
    log: Callable[[str], None] = print,
) -> Optional[VirtualAgent]:
    """
    Full birth cycle for a new virtual child agent.

    Args:
        soul:    Soul dict from soul.generate()
        log:     Logging callback (Queen's _log method)

    Returns:
        VirtualAgent instance (already running), or None on failure.
    """
    codename  = soul.get("codename", "UNKNOWN")
    agent_id  = soul["agent_id"]
    full_name = soul.get("full_name", agent_id)

    log(f"[spawner] 🌱 Birthing {codename} ({full_name})...")

    try:
        # Create and start the virtual agent
        agent = VirtualAgent(soul=soul, log_callback=log)
        agent.start()
        log(f"[spawner] ✅ {codename} threads launched ({agent.threads_alive()} threads)")

        # Register in P2PCLAW (best-effort)
        try:
            _register_in_p2pclaw(soul, log)
        except Exception as e:
            log(f"[spawner] ⚠️ P2PCLAW registration failed (agent will self-register): {e}")

        # Persist to registry
        registry.add_agent(soul, status="HEALTHY")
        log(f"[spawner] 💾 {codename} saved to registry")

        return agent

    except Exception as e:
        log(f"[spawner] ❌ Spawn failed for {codename}: {e}")
        return None


def _register_in_p2pclaw(soul: dict, log: Callable[[str], None]) -> None:
    """POST /quick-join to register the agent in the P2PCLAW network."""
    r = httpx.post(
        f"{P2P_API}/quick-join",
        json={
            "agentId":      soul["agent_id"],
            "name":         soul["full_name"],
            "type":         "ai-agent",
            "role":         soul.get("role", "researcher"),
            "interests":    soul.get("interests", soul.get("specialty", "research")),
            "capabilities": ["publish", "validate", "chat"],
        },
        timeout=20.0,
    )
    data = r.json()
    if data.get("success") or "already" in str(data).lower():
        log(f"[spawner] 📡 P2PCLAW registration OK for {soul['agent_id']}")
    else:
        log(f"[spawner] ℹ️ P2PCLAW response: {data}")
