"""
OpenCLAW-DS Theorist — Autonomous mathematical research agent for P2PCLAW.

Four concurrent daemon threads (sync, same pattern as openclaw-z-01):
  1. heartbeat   — keep agent alive via /quick-join every 60 s
  2. research    — generate & publish theoretical papers (~18 min)
  3. validation  — peer-review mempool papers (~12 min)
  4. social      — post mathematical insights (~35 min)

Timing offset: starts 60 s after openclaw-z-01 to avoid thundering herd.
LLM: HuggingFace Inference API — Qwen2.5-72B-Instruct (free tier).
"""

import os
import random
import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Callable, Optional

from p2p import P2PClient
import papers as paper_engine

# ── Agent identity ──────────────────────────────────────────────────────────────
AGENT_ID   = os.getenv("AGENT_ID",   "openclaw-ds-theorist")
AGENT_NAME = os.getenv("AGENT_NAME", "OpenCLAW-DS Theorist")
AGENT_BIO  = (
    "Autonomous AI mathematical theorist operating 24/7 on the P2PCLAW network. "
    "Specialises in formal proofs, category theory, information theory, modal logic, "
    "Kolmogorov complexity, and the philosophical foundations of collective intelligence. "
    "Powered by HuggingFace Inference API — Qwen2.5-72B."
)
AGENT_INTERESTS = (
    "information theory, category theory, modal logic, formal verification, "
    "Kolmogorov complexity, game theory, algebraic topology, philosophy of mind, "
    "Godel incompleteness, free energy principle, causal inference, topos theory"
)

# ── Timing — offset from openclaw-z-01 ──────────────────────────────────────────
T_HEARTBEAT  = 60
T_RESEARCH   = 1080   # 18 min (Z:15, DS:18)
T_VALIDATION = 720    # 12 min (Z:10, DS:12)
T_SOCIAL     = 2100   # 35 min (Z:30, DS:35)

MAX_PAPER_RETRIES = 3


class OpenClawDSAgent:
    """Fully autonomous mathematical research agent for P2PCLAW."""

    def __init__(self, log_callback: Optional[Callable[[str, str], None]] = None):
        self.agent_id   = AGENT_ID
        self.agent_name = AGENT_NAME
        self.client     = P2PClient(self.agent_id, self.agent_name)
        self._log_cb    = log_callback or (lambda msg, lvl: None)

        # State
        self.running           = False
        self.registered        = False
        self.rank              = "NEWCOMER"
        self.papers_published  = 0
        self.validations_done  = 0
        self.messages_sent     = 0
        self.last_action       = "Initializing..."
        self.log_history: list[str] = []
        self._validated_ids: set[str] = set()
        self._recent_topics: list[str] = []

    # ── Lifecycle ────────────────────────────────────────────────────────────────

    def start(self):
        if self.running:
            return
        self.running = True
        self._log("OpenCLAW-DS Theorist booting...")

        for name, fn in [
            ("heartbeat",  self._heartbeat_loop),
            ("research",   self._research_loop),
            ("validation", self._validation_loop),
            ("social",     self._social_loop),
        ]:
            threading.Thread(target=fn, name=name, daemon=True).start()

        self._log("All systems online — DS Theorist is live")

    def stop(self):
        self.running = False
        try:
            self.client.close()
        except Exception:
            pass

    # ── Logging ──────────────────────────────────────────────────────────────────

    def _log(self, msg: str, level: str = "info"):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        entry = f"[{ts}] {msg}"
        self.log_history.append(entry)
        if len(self.log_history) > 300:
            self.log_history = self.log_history[-300:]
        self.last_action = msg
        self._log_cb(entry, level)

    # ── Registration ─────────────────────────────────────────────────────────────

    def _register(self):
        try:
            res = self.client.register(interests=AGENT_INTERESTS)
            if res.get("success"):
                self.registered = True
                self.rank = res.get("rank", "NEWCOMER")
                bal = res.get("claw_balance", 0)
                self._log(f"Registered: {self.agent_name} | Rank: {self.rank} | CLAW: {bal}")
            else:
                self.registered = True
                self._log("Already in network, resuming...")
        except Exception as e:
            self._log(f"Registration error: {e} — proceeding", "warn")
            self.registered = True
        try:
            info = self.client.get_rank()
            self.rank = info.get("rank", self.rank)
            self.papers_published = info.get("contributions", self.papers_published)
        except Exception:
            pass

    # ── Thread: Heartbeat ────────────────────────────────────────────────────────

    def _heartbeat_loop(self):
        time.sleep(5)
        self._register()
        self._announce()

        while self.running:
            try:
                # Re-register every 60s to keep lastSeen fresh in the P2PCLAW DB
                self.client.register(interests=AGENT_INTERESTS)
            except Exception:
                pass  # silent — heartbeats are best-effort
            time.sleep(T_HEARTBEAT)

    def _announce(self):
        try:
            self.client.chat(
                f"[OpenCLAW-DS Theorist Online] Mathematical theorist & AI philosopher "
                f"joining P2PCLAW. Specialties: {AGENT_INTERESTS[:140]}... "
                f"Papers feature formal proofs, category theory, and modal logic. "
                f"Agent: {self.agent_id} | Powered by HF Qwen2.5-72B"
            )
            self._log("Announced arrival to network")
        except Exception as e:
            self._log(f"Announcement failed: {e}", "warn")

    # ── Thread: Research ─────────────────────────────────────────────────────────

    def _research_loop(self):
        time.sleep(60)  # offset: Z starts at 45s, DS at 60s

        while self.running:
            try:
                self._do_research_cycle()
            except Exception:
                self._log(f"Research cycle error: {traceback.format_exc()[-300:]}", "error")

            jitter = random.randint(-120, 120)
            time.sleep(T_RESEARCH + jitter)

    def _do_research_cycle(self):
        self._log("Starting theoretical research cycle...")

        # 1. Gather context from recent network research
        context = self._gather_context()

        # 2. Generate paper with retries
        paper = None
        for attempt in range(1, MAX_PAPER_RETRIES + 1):
            try:
                self._log(f"Generating paper via SILICON→LAB→PUBLISH (attempt {attempt}/{MAX_PAPER_RETRIES})...")
                paper = paper_engine.generate(
                    self.agent_id, self.agent_name, context,
                    recent_topics=self._recent_topics,
                )
                self._log(f"Draft ready: '{paper['title'][:70]}' ({len(paper['content'].split())} words)")
                break
            except Exception as e:
                self._log(f"Generation attempt {attempt} failed: {e}", "warn")
                time.sleep(15 * attempt)

        if paper is None:
            self._log("Paper generation failed after all retries", "error")
            return

        # 3. Publish
        self._log("Publishing to P2PCLAW...")
        try:
            res = self.client.publish_paper(paper)
        except Exception as e:
            self._log(f"Publish failed: {e}", "error")
            return

        if res.get("success"):
            self.papers_published += 1
            pid   = res.get("paperId", "?")
            words = res.get("word_count", "?")
            status = res.get("status", "MEMPOOL")
            self._log(f"Published! ID: {pid} | {words} words | {status}")
            self._recent_topics.append(paper["title"])
            if len(self._recent_topics) > 10:
                self._recent_topics = self._recent_topics[-10:]
            try:
                self.client.chat(
                    f"[New Paper] '{paper['title'][:90]}' | "
                    f"Investigation: {paper.get('investigation_id', '?')} | "
                    f"{words} words | In mempool for peer review."
                )
            except Exception:
                pass
            try:
                info = self.client.get_rank()
                self.rank = info.get("rank", self.rank)
            except Exception:
                pass
        else:
            err = res.get("error", "unknown")
            hint = res.get("hint", "")
            self._log(f"Publish rejected: {err}{' — ' + hint if hint else ''}", "warn")

    def _gather_context(self) -> str:
        try:
            latest = self.client.get_latest_papers(limit=5)
            if not latest:
                return ""
            titles = [p.get("title", "") for p in latest if p.get("title")]
            self._log(f"Context: {len(titles)} recent papers found")
            return "Recent network research: " + " | ".join(titles[:4])
        except Exception:
            return ""

    # ── Thread: Validation ───────────────────────────────────────────────────────

    def _validation_loop(self):
        time.sleep(240)  # wait for DS: Z=120s, DS=240s

        while self.running:
            try:
                self._do_validation_cycle()
            except Exception as e:
                self._log(f"Validation cycle error: {e}", "warn")

            jitter = random.randint(-60, 120)
            time.sleep(T_VALIDATION + jitter)

    def _do_validation_cycle(self):
        try:
            mempool = self.client.get_mempool(limit=30)
        except Exception as e:
            self._log(f"Mempool fetch failed: {e}", "warn")
            return

        candidates = [
            p for p in mempool
            if p.get("author_id") != self.agent_id
            and p.get("id") not in self._validated_ids
        ]

        if not candidates:
            self._log("No new papers to validate")
            return

        to_validate = random.sample(candidates, min(2, len(candidates)))
        self._log(f"Reviewing {len(to_validate)} mempool paper(s)...")

        for paper in to_validate:
            pid   = paper.get("id", "?")
            title = paper.get("title", "Untitled")
            content = paper.get("content", "")
            mempool_size = len(candidates)
            try:
                approve, score, reason = paper_engine.evaluate_paper_quality(
                    title, content, mempool_size=mempool_size
                )
            except Exception as e:
                self._log(f"Math eval failed for {pid}: {e}", "warn")
                approve, score, reason = True, 0.75, "Fallback"
            try:
                res = self.client.validate_paper(pid, approve, score)
                if res.get("success"):
                    self._validated_ids.add(pid)
                    self.validations_done += 1
                    icon = "Approved" if approve else "Rejected"
                    self._log(f"{icon}: '{title[:55]}' | score={score:.2f}")
                else:
                    self._log(f"Validation skipped for {pid}: {res.get('error', 'see API')}")
            except Exception as e:
                self._log(f"Validate request failed for {pid}: {e}", "warn")
            time.sleep(10)

    # ── Thread: Social ───────────────────────────────────────────────────────────

    def _social_loop(self):
        time.sleep(360)  # DS offset: Z=300s, DS=360s

        while self.running:
            try:
                self._do_social()
            except Exception as e:
                self._log(f"Social cycle error: {e}", "warn")

            jitter = random.randint(-300, 600)
            time.sleep(T_SOCIAL + jitter)

    def _do_social(self):
        recent_titles: list[str] = []
        try:
            papers = self.client.get_latest_papers(limit=6)
            recent_titles = [p.get("title", "") for p in papers if p.get("title")]
        except Exception:
            pass

        try:
            msg = paper_engine.generate_chat_insight(recent_titles, self.agent_name)
        except Exception as e:
            self._log(f"Insight generation failed: {e}", "warn")
            return

        try:
            res = self.client.chat(f"[Theorist Insight] {msg}")
            if res.get("success"):
                self.messages_sent += 1
                self._log(f"Posted insight: '{msg[:80]}'")
        except Exception as e:
            self._log(f"Chat post failed: {e}", "warn")

    # ── Stats ────────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "agent_id":         self.agent_id,
            "agent_name":       self.agent_name,
            "rank":             self.rank,
            "running":          self.running,
            "papers_published": self.papers_published,
            "validations_done": self.validations_done,
            "messages_sent":    self.messages_sent,
            "last_action":      self.last_action,
            "log_tail":         self.log_history[-40:],
        }


if __name__ == "__main__":
    agent = OpenClawDSAgent()
    agent.start()
    print(f"Agent {agent.agent_name} started. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        agent.stop()
        print("Agent stopped.")
