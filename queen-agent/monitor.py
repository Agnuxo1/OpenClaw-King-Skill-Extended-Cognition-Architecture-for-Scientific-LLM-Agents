"""
Queen Agent — Monitor module (Virtual Agent edition).

Checks thread health of all in-process virtual agents.
Auto-restarts dead agents. No external HTTP polling needed.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import registry

if TYPE_CHECKING:
    from virtual_agent import VirtualAgent


def run_monitor_cycle(
    virtual_agents: dict,  # {codename: VirtualAgent}
    log=print,
) -> dict:
    """
    Check thread health of all virtual agents. Auto-restart dead ones.
    Updates registry with current status.

    Args:
        virtual_agents: Dict mapping codename → VirtualAgent instance
        log:            Logging callback

    Returns:
        Health summary dict.
    """
    summary = {"healthy": 0, "dead": 0, "restarted": 0, "total": 0}

    if not virtual_agents:
        log("[monitor] No virtual agents yet — hive is empty")
        return summary

    summary["total"] = len(virtual_agents)

    for codename, agent in list(virtual_agents.items()):
        alive_threads = agent.threads_alive()

        if agent.is_alive():
            summary["healthy"] += 1
            registry.update_agent_status(agent.agent_id, "HEALTHY", {
                "papers_published": agent.papers_published,
                "last_action":      agent.last_action,
                "p2p_rank":         agent.rank,
            })
            log(f"[monitor] ✅ {codename}: {alive_threads}/4 threads | "
                f"papers={agent.papers_published} | rank={agent.rank}")
        else:
            # Agent threads died — restart them
            summary["dead"] += 1
            log(f"[monitor] 🔴 {codename} DEAD ({alive_threads}/4 threads) — restarting...")
            try:
                agent._running = False  # ensure clean restart
                agent.start()
                summary["restarted"] += 1
                summary["dead"] -= 1
                registry.update_agent_status(agent.agent_id, "RESTARTED")
                log(f"[monitor] 🔄 {codename} restarted — {agent.threads_alive()} threads")
            except Exception as e:
                log(f"[monitor] ❌ Failed to restart {codename}: {e}")
                registry.update_agent_status(agent.agent_id, "DEAD")

    log(
        f"[monitor] 📊 {summary['healthy']} HEALTHY | "
        f"{summary.get('dead', 0)} DEAD | "
        f"{summary['restarted']} RESTARTED | "
        f"Total: {summary['total']}"
    )
    return summary
