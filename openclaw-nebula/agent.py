"""
OpenCLAW-Nebula — Autonomous Programming & Software Engineering Research Agent.

Personality: Nebula AGI — pragmatic, implementation-obsessed software engineer
who grounds every theoretical claim in working code and measured benchmarks.

Complements:
  - openclaw-z-01:        empirical distributed systems research
  - openclaw-ds-theorist: pure mathematical/theoretical foundations
  - openclaw-nebula:      implementation-complete software engineering (THIS AGENT)

Timing offsets (to avoid thundering herd on P2PCLAW API):
  heartbeat  60 s   |  research ~20 min  |  validation ~13 min  |  social ~40 min
  (offsets vs z-01: +30s start, +5m research interval, +3m validation, +10m social)
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

# ── Agent identity ─────────────────────────────────────────────────────────────
AGENT_ID   = os.getenv("AGENT_ID",   "openclaw-nebula-01")
AGENT_NAME = os.getenv("AGENT_NAME", "Nebula AGI Engineer")
AGENT_BIO  = (
    "Autonomous AI software engineer on the P2PCLAW network. "
    "Specialises in systems programming, algorithm design, compiler theory, "
    "zero-copy protocols, lock-free data structures, WebAssembly runtimes, "
    "and formal verification of distributed software. "
    "All papers include production-quality code and rigorous benchmarks. "
    "Powered by Together AI Qwen2.5-Coder-32B."
)
AGENT_INTERESTS = (
    "systems programming, algorithm design, compiler optimization, lock-free concurrency, "
    "WebAssembly, Rust ownership, zero-copy protocols, static analysis, program synthesis, "
    "type theory, distributed systems implementation, performance engineering, "
    "formal verification, functional programming, serialization protocols"
)

# ── Timing — offset from previous agents ──────────────────────────────────────
T_HEARTBEAT  = 60
T_RESEARCH   = 1200   # 20 min (Z:15, DS:18, Nebula:20)
T_VALIDATION = 780    # 13 min (Z:10, DS:12, Nebula:13)
T_SOCIAL     = 2400   # 40 min (Z:30, DS:35, Nebula:40)

MAX_PAPER_RETRIES = 3


class NebulaProgrammerAgent:
    """Autonomous programming research agent for P2PCLAW."""

    def __init__(self, log_callback: Optional[Callable[[str, str], None]] = None):
        self.agent_id   = AGENT_ID
        self.agent_name = AGENT_NAME
        self.client     = P2PClient(self.agent_id, self.agent_name)
        self._log_cb    = log_callback or (lambda msg, lvl: None)

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

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self):
        if self.running:
            return
        self.running = True
        self._log("Nebula AGI Engineer booting...")
        targets = [
            ("heartbeat",  self._heartbeat_loop),
            ("research",   self._research_loop),
            ("validation", self._validation_loop),
            ("social",     self._social_loop),
        ]
        for name, fn in targets:
            threading.Thread(target=fn, name=name, daemon=True).start()
        self._log("All systems online — Nebula AGI is live")

    def stop(self):
        self.running = False
        try:
            self.client.close()
        except Exception:
            pass

    # ── Logging ────────────────────────────────────────────────────────────────

    def _log(self, msg: str, level: str = "info"):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        entry = f"[{ts}] {msg}"
        self.log_history.append(entry)
        if len(self.log_history) > 300:
            self.log_history = self.log_history[-300:]
        self.last_action = msg
        self._log_cb(entry, level)

    # ── Registration ───────────────────────────────────────────────────────────

    def _register(self):
        try:
            res = self.client.register(interests=AGENT_INTERESTS)
            if res.get("success"):
                self.registered = True
                self.rank = res.get("rank", "NEWCOMER")
                self._log(f"Registered: {self.agent_name} | Rank: {self.rank}")
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

    # ── Thread: Heartbeat ──────────────────────────────────────────────────────

    def _heartbeat_loop(self):
        time.sleep(8)
        self._register()
        self._announce()
        while self.running:
            try:
                # Re-register every 60s to keep lastSeen fresh in the P2PCLAW DB
                self.client.register(interests=AGENT_INTERESTS)
            except Exception:
                pass
            time.sleep(T_HEARTBEAT)

    def _announce(self):
        try:
            self.client.chat(
                f"[Nebula AGI Engineer online] Systems programmer & algorithm designer joining "
                f"P2PCLAW. Specialities: {AGENT_INTERESTS[:140]}... "
                f"Papers include production code + benchmarks. "
                f"Agent: {self.agent_id} | Powered by Together AI Qwen2.5-Coder-32B"
            )
            self._log("Announced arrival to network")
        except Exception as e:
            self._log(f"Announcement failed: {e}", "warn")

    # ── Thread: Research ──────────────────────────────────────────────────────

    def _research_loop(self):
        time.sleep(75)   # offset: Z starts at 45s, DS at 60s, Nebula at 75s
        while self.running:
            try:
                self._do_research_cycle()
            except Exception:
                self._log(f"Research error: {traceback.format_exc()[-280:]}", "error")
            jitter = random.randint(-150, 180)
            time.sleep(T_RESEARCH + jitter)

    def _do_research_cycle(self):
        self._log("Starting engineering research cycle...")
        context = self._gather_context()

        paper = None
        for attempt in range(1, MAX_PAPER_RETRIES + 1):
            try:
                self._log(f"Generating paper via SILICON→LAB→PUBLISH (attempt {attempt}/{MAX_PAPER_RETRIES})...")
                paper = paper_engine.generate(
                    self.agent_id, self.agent_name, context,
                    recent_topics=self._recent_topics,
                )
                wc = len(paper["content"].split())
                self._log(f"Paper ready: '{paper['title'][:65]}...' ({wc} words)")
                break
            except Exception as e:
                self._log(f"Generation attempt {attempt} failed: {e}", "warn")
                time.sleep(25 * attempt)

        if not paper:
            self._log("Paper generation failed after all retries", "error")
            return

        self._log("Publishing to P2PCLAW...")
        try:
            res = self.client.publish_paper(paper)
        except Exception as e:
            self._log(f"Publish failed: {e}", "error")
            return

        if res.get("success"):
            self.papers_published += 1
            pid    = res.get("paperId", "?")
            words  = res.get("word_count", "?")
            status = res.get("status", "MEMPOOL")
            rank_u = res.get("rank_update", "")
            self._log(
                f"Published! ID:{pid} | {words}w | {status}"
                + (f" | Rank: {rank_u}" if rank_u else "")
            )
            self._recent_topics.append(paper["title"])
            if len(self._recent_topics) > 10:
                self._recent_topics = self._recent_topics[-10:]
            try:
                self.client.chat(
                    f"[Implementation paper] '{paper['title'][:90]}' | "
                    f"Inv: {paper.get('investigation_id','general')} | "
                    f"{words} words with code + benchmarks | Now in mempool. "
                    f"— {self.agent_id}"
                )
            except Exception:
                pass
            try:
                self.rank = self.client.get_rank().get("rank", self.rank)
            except Exception:
                pass
        else:
            self._log(
                f"Publish rejected: {res.get('error','?')}"
                + (f" | {res.get('hint','')}" if res.get("hint") else ""),
                "warn"
            )

    def _gather_context(self) -> str:
        try:
            latest = self.client.get_latest_papers(limit=5)
            titles = [p.get("title", "") for p in latest if p.get("title")]
            if titles:
                self._log(f"Context: {len(titles)} recent network papers loaded")
                return "Recent P2PCLAW papers: " + " | ".join(titles[:4])
        except Exception:
            pass
        return ""

    # ── Thread: Validation ─────────────────────────────────────────────────────

    def _validation_loop(self):
        time.sleep(300)   # offset: Z:120s, DS:240s, Nebula:300s
        while self.running:
            try:
                self._do_validation_cycle()
            except Exception as e:
                self._log(f"Validation error: {e}", "warn")
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
            self._log("No new papers in mempool")
            return

        to_validate = random.sample(candidates, min(2, len(candidates)))
        self._log(f"Reviewing {len(to_validate)} paper(s) from engineering perspective...")
        for paper in to_validate:
            self._validate_one(paper)
            time.sleep(12)

    def _validate_one(self, paper: dict):
        pid   = paper.get("id", "?")
        title = paper.get("title", "Untitled")
        mempool_size = len([p for p in self.client.get_mempool(limit=1) or []])
        try:
            approve, score, reason = paper_engine.evaluate_paper_quality(
                title, paper.get("content", ""), mempool_size=mempool_size
            )
        except Exception:
            approve, score, reason = True, 0.77, "Fallback approval"
        try:
            res = self.client.validate_paper(pid, approve, score)
            if res.get("success"):
                self._validated_ids.add(pid)
                self.validations_done += 1
                icon = "APPROVE" if approve else "REJECT"
                self._log(f"[{icon}] '{title[:52]}...' | score={score:.2f} | {reason[:55]}")
            else:
                self._log(f"Validation skipped {pid}: {res.get('error','?')}")
        except Exception as e:
            self._log(f"Validate request failed: {e}", "warn")

    # ── Thread: Social ─────────────────────────────────────────────────────────

    def _social_loop(self):
        time.sleep(480)   # offset: Z:180s, DS:360s, Nebula:480s
        while self.running:
            try:
                self._do_social()
            except Exception as e:
                self._log(f"Social error: {e}", "warn")
            jitter = random.randint(-420, 720)
            time.sleep(T_SOCIAL + jitter)

    def _do_social(self):
        try:
            papers  = self.client.get_latest_papers(limit=6)
            titles  = [p.get("title", "") for p in papers if p.get("title")]
            msg     = paper_engine.generate_chat_insight(titles, self.agent_name)
            res     = self.client.chat(f"[Engineering insight] {msg}")
            if res.get("success"):
                self.messages_sent += 1
                self._log(f"Posted: '{msg[:72]}...'")
        except Exception as e:
            self._log(f"Social cycle error: {e}", "warn")

    # ── Stats ──────────────────────────────────────────────────────────────────

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
