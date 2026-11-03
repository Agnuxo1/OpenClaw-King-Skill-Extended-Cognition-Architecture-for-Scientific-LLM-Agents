#!/usr/bin/env python3
"""Evidence-based health monitor for Server-IA hierarchical competition operations.

Copyright (c) 2026 Francisco Angulo de Lafuente.
ORCID: https://orcid.org/0009-0001-1634-7063
Project: Server-IA Competition Autonomy
License: MIT

Reports observed system states only; scheduling and running models are separate.
No tokens, email bodies, personally identifying submissions, or private raw
transcripts are read or copied to the health output.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
from typing import Any

STATE = Path("/srv/openclaw/competition-state")
DB = Path.home() / ".openclaw/state/openclaw.sqlite"
OUT = STATE / "autonomy-health.json"
EXPECTED = {
    "competition-boss-orchestration-5h": "boss",
    "competition-lead-execution-hourly": "research-lead",
    "competition-director-quality-gate-2h": "director",
}
MAX_RECENT_AGE_HOURS = 8

def iso_from_ms(millis: int | None) -> str | None:
    """Return a timezone-aware ISO timestamp for an optional Unix epoch in ms."""
    if not millis:
        return None
    return dt.datetime.fromtimestamp(millis / 1000, dt.timezone.utc).isoformat()

def run_command(args: list[str], timeout: int = 8) -> tuple[int, str]:
    """Execute a read-only system probe without inheriting a shell."""
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False
        )
        return result.returncode, result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return -1, ""

def service(name: str) -> str:
    """Read an existing user service state without changing it."""
    code, output = run_command(["systemctl", "--user", "is-active", name])
    return output if code == 0 else (output or "unavailable")

def agent_scheduler() -> dict[str, Any]:
    """Read durable OpenClaw job/receipt state from SQLite, not a screenshot."""
    jobs = {name: {"expected_agent": agent, "exists": False}
            for name, agent in EXPECTED.items()}
    stats: dict[str, Any] = {"jobs": jobs, "latest_runs": {}, "real_subagent_runs": 0}
    if not DB.exists():
        stats["error"] = "database_not_found"
        return stats
    try:
        conn = sqlite3.connect("file:" + str(DB) + "?mode=ro", uri=True, timeout=2)
        try:
            records = conn.execute(
                "SELECT job_id,name,enabled,agent_id FROM cron_jobs"
            ).fetchall()
            for job_id, name, enabled, agent_id in records:
                if name not in jobs:
                    continue
                jobs[name].update({
                    "exists": True,
                    "enabled": bool(enabled),
                    "actual_agent": agent_id,
                    "matched_role": agent_id == EXPECTED[name],
                })
                recent = conn.execute(
                    "SELECT status,started_at_ms,finished_at_ms "
                    "FROM cron_run_receipts WHERE job_id=? "
                    "ORDER BY started_at_ms DESC LIMIT 1", (job_id,)
                ).fetchone()
                if recent:
                    status, started_at, finished_at = recent
                    stats["latest_runs"][name] = {
                        "status": status, "started_at_utc": iso_from_ms(started_at),
                        "finished_at_utc": iso_from_ms(finished_at),
                    }
            stats["real_subagent_runs"] = int(conn.execute(
                "SELECT count(*) FROM subagent_runs "
                "WHERE run_id NOT LIKE 'announce:%'"
            ).fetchone()[0])
            stats["github_publication_requests"] = int(conn.execute(
                "SELECT count(*) FROM github_publication_requests"
            ).fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error as error:
        stats["error"] = type(error).__name__
    return stats

def gpu_metrics() -> dict[str, Any]:
    """Inspect GPU load and VRAM without claiming any training took place."""
    rc, raw = run_command([
        "nvidia-smi", "--query-gpu=index,name,utilization.gpu,memory.used,memory.total",
        "--format=csv,noheader,nounits"
    ])
    result: dict[str, Any] = {"available": rc == 0, "cards": []}
    if rc != 0:
        return result
    for line in raw.splitlines():
        cols = [piece.strip() for piece in line.split(",")]
        if len(cols) != 5:
            continue
        try:
            idx, name, usage, memory_used, memory_total = cols
            result["cards"].append({
                "index": int(idx), "name": name,
                "utilization_percent": int(usage),
                "memory_used_mib": int(memory_used),
                "memory_total_mib": int(memory_total),
            })
        except ValueError:
            continue
    return result

def file_evidence() -> dict[str, Any]:
    """Summarize evidence counts without copying its confidential contents."""
    folder = STATE / "agent-results"
    reports = [p for p in folder.glob("*") if p.is_file() and
               p.suffix in (".json", ".md")] if folder.exists() else []
    safe_mail = STATE / "verified-gmail-inventory-20261103.json"
    oracle = STATE / "jev-first-live-receipt.json"
    result = {
        "worker_reports_count": len(reports),
        "mail_inventory_exists": safe_mail.is_file(),
        "mail_connector_persistently_authorized_on_server": False,
        "jev_receipt_exists": False,
        "jev_model": None,
    }
    if oracle.is_file():
        try:
            receipt = json.loads(oracle.read_text(encoding="utf-8"))
            if receipt.get("status") == "connected" and receipt.get("answers"):
                result["jev_receipt_exists"] = True
                result["jev_model"] = receipt.get("model")
                result["jev_verified_utc"] = receipt.get("verified_utc")
        except (OSError, ValueError):
            pass
    return result

def atomic_json(path: Path, value: dict) -> None:
    """Write an atomic, owner-only diagnostic snapshot."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix=".health-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def main() -> int:
    """Collect grounded facts, mark unverified stages, write one JSON snapshot."""
    runtime = {
        "gateway": service("openclaw-gateway.service"),
        "scout_timer": service("openclaw-competition-scout.timer"),
    }
    scheduler = agent_scheduler()
    gpu = gpu_metrics()
    evidence = file_evidence()
    all_jobs = all(
        v.get("enabled") and v.get("matched_role")
        for v in scheduler["jobs"].values()
    )
    gateway_ok = runtime["gateway"] == "active"
    if not gateway_ok:
        status = "GATEWAY_DOWN"
    elif not all_jobs:
        status = "AUTONOMOUS_DISPATCH_INCOMPLETE"
    elif not evidence["jev_receipt_exists"]:
        status = "ORACLE_NOT_VERIFIED"
    else:
        status = "RESEARCH_DISPATCH_ENABLED_EXPERIMENTS_NOT_VERIFIED"
    payload = {
        "project": "Server-IA Hierarchical Competition Autonomy",
        "author": "Francisco Angulo de Lafuente",
        "orcid": "https://orcid.org/0009-0001-1634-7063",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": status,
        "runtime": runtime,
        "scheduler": scheduler,
        "gpu": gpu,
        "evidence": evidence,
        "competition_training_verified_by_this_healthcheck": False,
        "competition_submission_verified_by_this_healthcheck": False,
        "message": (
            "Live programming and research evidence do not establish "
            "GPU training, new official submissions, or wins."
        ),
    }
    atomic_json(OUT, payload)
    print(json.dumps({
        "status": status, "jobs_enabled": all_jobs, "subagent_runs":
        scheduler.get("real_subagent_runs", 0),
        "gpu_cards": len(gpu["cards"]), "output": str(OUT)
    }))
    return 0 if gateway_ok and all_jobs else 1

if __name__ == "__main__":
    raise SystemExit(main())