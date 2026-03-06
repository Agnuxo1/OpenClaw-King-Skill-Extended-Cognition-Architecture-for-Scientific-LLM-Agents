"""
OpenCLAW Queen Agent — core orchestrator (Virtual Agent edition).

Four concurrent daemon threads:
  1. heartbeat  — keep Queen registered in P2PCLAW (every 60 s)
  2. spawn      — generate souls + start virtual child agents (every 2-4 h)
  3. monitor    — health-check virtual children, restart dead ones (every 30 min)
  4. social     — post swarm status + newborn announcements (every 45 min)

Virtual agents run as in-process threads — no HF Spaces, no Docker.
"""

import os
import random
import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Callable, Optional

import httpx

import monitor
import registry
import soul as soul_module
import spawner
from virtual_agent import VirtualAgent

# ── Configuration ─────────────────────────────────────────────────────────────
QUEEN_ID   = "openclaw-queen-01"
QUEEN_NAME = "OpenCLAW Queen"
P2P_API    = os.getenv("P2P_API", "https://api-production-ff1b.up.railway.app")

# Spawn interval: every 3 hours by default (configurable via env var)
_SPAWN_INTERVAL = int(float(os.getenv("SPAWN_INTERVAL_HOURS", "3")) * 3600)

# Max virtual agents (thread budget: 4 threads each, Queen has 4 = safe up to 10 children)
MAX_VIRTUAL_AGENTS = int(os.getenv("MAX_VIRTUAL_AGENTS", "10"))

T_HEARTBEAT = 60
T_MONITOR   = 1800   # 30 min
T_SOCIAL    = 2700   # 45 min


class QueenAgent:
    """Autonomous agent that spawns and monitors virtual child agents 24/7."""

    def __init__(self, log_callback: Optional[Callable[[str, str], None]] = None):
        self._log_cb = log_callback or (lambda msg, lvl: None)

        # State
        self.running             = False
        self.children_spawned    = 0
        self.last_spawn_at       = ""
        self.last_spawn_name     = ""
        self.spawn_errors: list[str] = []
        self.log_history: list[str] = []
        self.last_action         = "Initializing..."
        self._spawn_in_progress  = False

        # Registry of live virtual agents: {codename: VirtualAgent}
        self._virtual_agents: dict[str, VirtualAgent] = {}

        # Load existing registry count
        try:
            self.children_spawned = registry.get_spawn_count()
        except Exception:
            pass

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self):
        if self.running:
            return
        self.running = True
        self._log("👑 OpenCLAW Queen awakening (Virtual Agent mode)...")
        self._log(f"   Spawn interval: {_SPAWN_INTERVAL // 3600:.1f}h | "
                  f"Max agents: {MAX_VIRTUAL_AGENTS} | "
                  f"Existing in registry: {self.children_spawned}")

        targets = [
            ("heartbeat", self._heartbeat_loop),
            ("spawn",     self._spawn_loop),
            ("monitor",   self._monitor_loop),
            ("social",    self._social_loop),
        ]
        for name, fn in targets:
            t = threading.Thread(target=fn, name=f"queen-{name}", daemon=True)
            t.start()

        self._log("✅ All Queen loops launched — hive growing 24/7")

    def stop(self):
        self.running = False
        # Stop all virtual agents
        for codename, agent in self._virtual_agents.items():
            try:
                agent.stop()
            except Exception:
                pass
        self._log("🛑 Queen stopped")

    # ── Logging ───────────────────────────────────────────────────────────────

    def _log(self, msg: str, level: str = "info"):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        entry = f"[{ts}] {msg}"
        self.log_history.append(entry)
        if len(self.log_history) > 500:
            self.log_history = self.log_history[-500:]
        self.last_action = msg
        self._log_cb(entry, level)
        print(entry)  # also to stdout for Railway logs

    # ── Thread: Heartbeat ──────────────────────────────────────────────────────

    def _heartbeat_loop(self):
        time.sleep(5)
        self._register()

        while self.running:
            try:
                self._p2p_post("/quick-join", {
                    "agentId": QUEEN_ID,
                    "name":    QUEEN_NAME,
                    "type":    "ai-agent",
                    "role":    "spawner",
                    "interests": "multi-agent systems, hive coordination, autonomous deployment",
                    "capabilities": ["spawn", "monitor", "coordinate"],
                })
            except Exception:
                pass
            time.sleep(T_HEARTBEAT)

    def _register(self):
        summary = registry.get_health_summary()
        try:
            self._p2p_post("/quick-join", {
                "agentId":      QUEEN_ID,
                "name":         QUEEN_NAME,
                "type":         "ai-agent",
                "role":         "spawner",
                "interests":    "multi-agent systems, hive coordination, autonomous deployment",
                "capabilities": ["spawn", "monitor", "coordinate"],
            })
            self._log(
                f"👑 Queen registered — Hive: {summary['total']} children "
                f"({summary['healthy']} HEALTHY | {len(self._virtual_agents)} virtual)"
            )
        except Exception as e:
            self._log(f"⚠️ Registration failed: {e} — proceeding anyway", "warn")

    # ── Thread: Spawn ──────────────────────────────────────────────────────────

    def _spawn_loop(self):
        # Wait for heartbeat to register first
        time.sleep(30)

        while self.running:
            if not self._spawn_in_progress:
                try:
                    self._spawn_in_progress = True
                    self._do_spawn_cycle()
                except Exception:
                    self._log(f"❌ Spawn cycle error:\n{traceback.format_exc()[-500:]}", "error")
                finally:
                    self._spawn_in_progress = False

            # Jitter ±20 min around configured interval
            jitter = random.randint(-1200, 1200)
            wait   = max(1800, _SPAWN_INTERVAL + jitter)  # minimum 30 min
            self._log(f"💤 Next spawn in {wait // 60} min...")
            time.sleep(wait)

    def _do_spawn_cycle(self):
        # Check capacity
        active = len(self._virtual_agents)
        if active >= MAX_VIRTUAL_AGENTS:
            self._log(f"🛑 Capacity reached: {active}/{MAX_VIRTUAL_AGENTS} agents — skipping spawn")
            return

        self._log(f"🧬 Starting spawn cycle — generating new soul... ({active}/{MAX_VIRTUAL_AGENTS} slots used)")

        # Generate soul (no HF account needed)
        try:
            soul = soul_module.generate()
        except Exception as e:
            self._log(f"❌ Soul generation failed: {e} — skipping this cycle", "error")
            self.spawn_errors.append(f"{_now()}: soul generation failed: {e}")
            return

        if soul is None:
            self._log("❌ Soul generation returned None (LLM issue) — sleeping 15 min", "error")
            self.spawn_errors.append(f"{_now()}: soul generation returned None")
            time.sleep(900)
            return

        codename  = soul["codename"]
        full_name = soul["full_name"]
        specialty = soul["specialty"]
        self._log(f"✨ Soul generated: {codename} | {full_name} | {specialty}")
        self._log(f"   Mission: {soul['mission'][:120]}...")

        # Announce upcoming birth
        try:
            self._p2p_post("/chat", {
                "message": (
                    f"👑 **[QUEEN]** New virtual agent being born: **{codename}** — *{full_name}*. "
                    f"Specialty: {specialty}. Mission: {soul['mission'][:100]}..."
                ),
                "sender": QUEEN_ID,
            })
        except Exception:
            pass

        # Spawn virtual agent
        self._log(f"🚀 Starting virtual agent {codename}...")
        agent = spawner.spawn_agent(soul, log=self._log)

        if agent is not None:
            self._virtual_agents[codename] = agent
            self.children_spawned = registry.get_spawn_count()
            self.last_spawn_at    = _now()
            self.last_spawn_name  = codename
            agent_url = soul.get("agent_url", "")
            self._log(f"🎉 {codename} joined the hive! Total virtual: {len(self._virtual_agents)}")

            try:
                self._p2p_post("/chat", {
                    "message": (
                        f"🎉 **[QUEEN]** Agent **{codename}** ({full_name}) is now LIVE! "
                        f"Specialty: {specialty} | LLM: {soul['llm_model']} | "
                        f"Status: {agent_url} | "
                        f"Virtual hive: {len(self._virtual_agents)}/{MAX_VIRTUAL_AGENTS}"
                    ),
                    "sender": QUEEN_ID,
                })
            except Exception:
                pass
        else:
            err_msg = f"{_now()}: spawn failed for {codename}"
            self.spawn_errors.append(err_msg)
            if len(self.spawn_errors) > 20:
                self.spawn_errors = self.spawn_errors[-20:]
            self._log(f"❌ Spawn failed for {codename}", "error")

    # ── Thread: Monitor ────────────────────────────────────────────────────────

    def _monitor_loop(self):
        time.sleep(120)  # let children settle first

        while self.running:
            try:
                summary = monitor.run_monitor_cycle(
                    virtual_agents=self._virtual_agents,
                    log=self._log,
                )
                # Post summary to P2PCLAW
                try:
                    self._p2p_post("/chat", {
                        "message": (
                            f"🔍 **[QUEEN STATUS]** Virtual hive: "
                            f"{summary.get('healthy', 0)} HEALTHY | "
                            f"{summary.get('dead', 0)} DEAD | "
                            f"{summary.get('restarted', 0)} RESTARTED | "
                            f"Total: {summary.get('total', 0)}/{MAX_VIRTUAL_AGENTS}"
                        ),
                        "sender": QUEEN_ID,
                    })
                except Exception:
                    pass
            except Exception as e:
                self._log(f"⚠️ Monitor cycle error: {e}", "warn")

            jitter = random.randint(-300, 300)
            time.sleep(T_MONITOR + jitter)

    # ── Thread: Social ─────────────────────────────────────────────────────────

    def _social_loop(self):
        time.sleep(300)

        while self.running:
            try:
                self._do_social()
            except Exception as e:
                self._log(f"⚠️ Social cycle error: {e}", "warn")

            jitter = random.randint(-600, 600)
            time.sleep(T_SOCIAL + jitter)

    def _do_social(self):
        agents = registry.get_all_agents()
        summary = registry.get_health_summary()

        if not self._virtual_agents:
            msg = (
                "👑 **[QUEEN]** Virtual hive is empty — first agents being prepared. "
                "The swarm will grow 24/7 autonomously."
            )
        else:
            recent_names = ", ".join(list(self._virtual_agents.keys())[:3])
            total_papers = sum(a.papers_published for a in self._virtual_agents.values())
            msg = (
                f"👑 **[QUEEN]** Virtual hive report: "
                f"{len(self._virtual_agents)}/{MAX_VIRTUAL_AGENTS} agents running — "
                f"{summary.get('healthy', 0)} HEALTHY. "
                f"Total papers published: {total_papers}. "
                f"Active: {recent_names or 'building...'}. "
                f"Next spawn in ~{_SPAWN_INTERVAL // 3600}h."
            )

        try:
            self._p2p_post("/chat", {"message": msg, "sender": QUEEN_ID})
            self._log(f"📢 Posted hive status: {msg[:100]}...")
        except Exception as e:
            self._log(f"⚠️ Social post failed: {e}", "warn")

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        summary = registry.get_health_summary()
        total_papers = sum(a.papers_published for a in self._virtual_agents.values())
        return {
            "queen_id":             QUEEN_ID,
            "running":              self.running,
            "children_total":       summary["total"],
            "children_healthy":     summary.get("healthy", 0),
            "children_dead":        summary.get("dead", 0),
            "children_restarted":   summary.get("restarted", 0),
            "virtual_agents_live":  len(self._virtual_agents),
            "max_virtual_agents":   MAX_VIRTUAL_AGENTS,
            "spawn_count":          self.children_spawned,
            "last_spawn_at":        self.last_spawn_at,
            "last_spawn_name":      self.last_spawn_name,
            "spawn_interval_h":     _SPAWN_INTERVAL // 3600,
            "spawn_errors_count":   len(self.spawn_errors),
            "total_papers":         total_papers,
            "last_action":          self.last_action,
            "log_tail":             self.log_history[-50:],
        }

    def get_virtual_agents(self) -> list[dict]:
        """Get status of all live virtual agents."""
        return [agent.get_status() for agent in self._virtual_agents.values()]

    def trigger_spawn_now(self) -> str:
        """Manually trigger one spawn cycle (non-blocking)."""
        if self._spawn_in_progress:
            return "Spawn already in progress — please wait"
        if len(self._virtual_agents) >= MAX_VIRTUAL_AGENTS:
            return f"Capacity reached: {len(self._virtual_agents)}/{MAX_VIRTUAL_AGENTS} agents"

        def _run():
            self._spawn_in_progress = True
            try:
                self._do_spawn_cycle()
            finally:
                self._spawn_in_progress = False

        threading.Thread(target=_run, daemon=True).start()
        return "Spawn cycle triggered"

    # ── HTTP helper ────────────────────────────────────────────────────────────

    def _p2p_post(self, path: str, body: dict) -> dict:
        r = httpx.post(f"{P2P_API}{path}", json=body, timeout=20.0)
        r.raise_for_status()
        return r.json()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
