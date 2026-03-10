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

import evolve
import llm as llm_module
import monitor
import persist
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
T_EVOLVE    = 7200   # 2 hours


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
                  f"Existing in registry: {self.children_spawned} | "
                  f"KV backup: {'ON' if persist.is_enabled() else 'OFF (set CF_API_TOKEN)'}")

        # Restore virtual agents from previous run (cloud KV → file fallback)
        self._restore_agents()

        targets = [
            ("heartbeat", self._heartbeat_loop),
            ("spawn",     self._spawn_loop),
            ("monitor",   self._monitor_loop),
            ("social",    self._social_loop),
            ("evolve",    self._evolve_loop),
        ]
        for name, fn in targets:
            t = threading.Thread(target=fn, name=f"queen-{name}", daemon=True)
            t.start()

        self._log("✅ All Queen loops launched — hive growing 24/7")

    def stop(self):
        self.running = False
        # Persist souls to CF KV before stopping
        self._backup_souls("shutdown")
        # Stop all virtual agents
        for codename, agent in self._virtual_agents.items():
            try:
                agent.stop()
            except Exception:
                pass
        self._log("🛑 Queen stopped")

    # ── Soul Persistence ───────────────────────────────────────────────────────

    def _restore_agents(self):
        """
        Restore virtual agents from previous run.
        Tries CF KV first (cloud-persistent), falls back to local registry file.
        Skips any codename already in _virtual_agents (safety guard).
        """
        # 1. Try CF KV (survives Railway redeploys)
        souls = persist.load_souls()
        source = "CF KV"

        # 2. Fallback: local registry (survives same-container in-process restart)
        if not souls:
            souls = registry.get_souls_for_restore()
            source = "local registry"

        if not souls:
            self._log("ℹ️ No souls to restore — hive starts fresh")
            return

        self._log(f"🔄 Restoring {len(souls)} agent(s) from {source}...")
        restored = 0
        for soul in souls:
            codename = soul.get("codename", "")
            if not codename or codename in self._virtual_agents:
                continue
            if len(self._virtual_agents) >= MAX_VIRTUAL_AGENTS:
                self._log(f"⚠️ Capacity reached during restore — skipping {codename}")
                break
            try:
                agent = spawner.spawn_agent(soul, log=self._log)
                if agent is not None:
                    self._virtual_agents[codename] = agent
                    restored += 1
            except Exception as e:
                self._log(f"⚠️ Failed to restore {codename}: {e}")

        if restored:
            self._log(f"✅ Restored {restored}/{len(souls)} virtual agent(s) from {source}")
        else:
            self._log(f"ℹ️ Could not restore any agents from {source} (souls invalid or capacity full)")

    def _backup_souls(self, trigger: str = "spawn") -> None:
        """Push current souls to CF KV. Best-effort, never raises."""
        if not self._virtual_agents:
            return
        souls = [agent.soul for agent in self._virtual_agents.values()]
        ok = persist.save_souls(souls)
        if ok:
            self._log(f"☁️ Souls backed up to CF KV ({len(souls)} agents, trigger={trigger})")
        elif persist.is_enabled():
            self._log(f"⚠️ CF KV backup failed (trigger={trigger})")

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

        self._log(f"🧬 Starting spawn cycle ({active}/{MAX_VIRTUAL_AGENTS} slots used)")

        # Prefer evolved soul from pool; fall back to fresh generation
        evolved_soul = registry.pop_evolved_soul()
        if evolved_soul:
            self._log(f"🔬 Using evolved soul from pool: {evolved_soul.get('codename')} "
                      f"(lineage: {evolved_soul.get('lineage', [])})")
            soul = evolved_soul
        else:
            self._log("✨ No evolved souls in pool — generating fresh soul...")
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
            # Backup souls to CF KV after each new spawn
            self._backup_souls("spawn")

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

            # Periodic soul backup (every monitor cycle ~30 min)
            self._backup_souls("monitor")

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

    # ── Thread: Evolve ─────────────────────────────────────────────────────────

    def _evolve_loop(self):
        """Evolution engine: runs every ~2h. Selects elites, mutates, crosses over."""
        # First run after 2h — give agents time to accumulate metrics
        time.sleep(T_EVOLVE)

        while self.running:
            try:
                self._do_evolve()
            except Exception as e:
                self._log(f"⚠️ Evolution cycle error: {e}", "warn")

            jitter = random.randint(-1800, 1800)
            time.sleep(max(3600, T_EVOLVE + jitter))

    def _do_evolve(self):
        if not self._virtual_agents:
            self._log("[EVOLVE] No virtual agents yet — skipping evolution cycle")
            return

        # 1. Rank all agents by fitness
        rankings = evolve.compute_rankings(self._virtual_agents)
        self._log(
            f"[EVOLVE] Generation {registry.get_generation()} — "
            f"ranking {len(rankings)} agents. "
            f"Top: {rankings[0]['codename']} fitness={rankings[0]['fitness']:.1f}"
            if rankings else "[EVOLVE] No rankings available"
        )

        if len(rankings) < 2:
            self._log("[EVOLVE] Need ≥2 agents for evolution — skipping this cycle")
            return

        # 2. Log fitness for top agents
        for entry in rankings[:5]:
            try:
                registry.log_fitness(entry["codename"], entry["fitness"])
            except Exception:
                pass

        # 3. Select élites
        elites = evolve.select_elites(rankings)
        self._log(f"[EVOLVE] {len(elites)} élite(s) selected for improvement")

        # 4. Mutate up to 3 élites to fix weaknesses
        pool_before = len(registry.get_evolved_pool())
        for elite_data in elites[:3]:
            soul       = elite_data["soul"]
            weaknesses = evolve.identify_weaknesses(soul, elite_data)
            if weaknesses:
                self._log(f"[EVOLVE] Mutating {soul.get('codename')} — weaknesses: {weaknesses}")
                mutated = evolve.mutate_soul(soul, weaknesses, llm_module.complete, self._log)
                registry.add_to_evolved_pool(mutated)

        # 5. Crossover top 2 élites → new hybrid offspring
        if len(elites) >= 2:
            gen = registry.get_generation()
            child = evolve.crossover_souls(
                elites[0]["soul"], elites[1]["soul"],
                llm_module.complete,
                generation=gen,
                log_fn=self._log,
            )
            registry.add_to_evolved_pool(child)
            self._log(f"[EVOLVE] Crossover offspring: {child.get('codename')}")

        # 6. Retire persistent bottom performers (only if above minimum)
        retired_codenames = evolve.retire_weak(self._virtual_agents, rankings, min_agents=3)
        for codename in retired_codenames:
            registry.mark_retired(codename)
            agent = self._virtual_agents.pop(codename, None)
            if agent:
                agent._running = False
                self._log(f"[EVOLVE] Retired underperformer: {codename}")

        # 7. Increment generation counter + persist
        gen = registry.increment_generation()
        self._backup_souls("evolve")

        # 8. Broadcast evolution report to P2PCLAW
        pool_size   = len(registry.get_evolved_pool())
        top_name    = rankings[0]["codename"] if rankings else "N/A"
        top_fitness = rankings[0]["fitness"]  if rankings else 0.0
        report = (
            f"🧬 **[QUEEN EVOLUTION]** Gen {gen}: "
            f"{len(elites)} élite(s) selected | "
            f"{pool_size - pool_before} new evolved souls in pool ({pool_size} total) | "
            f"{len(retired_codenames)} retired | "
            f"Top performer: **{top_name}** (fitness={top_fitness:.1f})"
        )
        try:
            self._p2p_post("/chat", {"message": report, "sender": QUEEN_ID})
        except Exception:
            pass
        self._log(report)

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        summary      = registry.get_health_summary()
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
            "evolution_generation": registry.get_generation(),
            "evolved_pool_size":    len(registry.get_evolved_pool()),
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
