#!/usr/bin/env python3
"""Audited, bounded TypeSafe JEV oracle for the Server-IA OpenClaw hierarchy.

Inputs and receipts remain under the protected competition-state directory.
The API credential is never passed on the CLI, included in responses, or logged.
Project: Server-IA Competition Oracle Bridge
Author: Francisco Angulo de Lafuente
ORCID: https://orcid.org/0009-0001-1634-7063
License: MIT
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

ROOT = Path("/srv/openclaw/competition-state").resolve()
KEY_PATH = Path("/home/ai/.openclaw/jev.key")
MODEL = "jev-latest"
MAX_INPUT_BYTES = 60000
MAX_QUESTIONS = 8
MAX_CRITERIA = 14

def protected_path(raw: str) -> Path:
    """Restrict file access to the dedicated competition state directory."""
    path = Path(raw).expanduser().resolve()
    if path != ROOT and ROOT not in path.parents:
        raise ValueError("Only competition-state paths are permitted")
    return path

def load_object(raw: str) -> dict:
    """Load a bounded UTF-8 JSON object from a safe path."""
    path = protected_path(raw)
    if not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("Missing or oversized input JSON")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Input must be a JSON object")
    return data

def compile_questions(spec: dict) -> dict:
    """Compile portable question descriptions to supported SDK types."""
    if not 1 <= len(spec) <= MAX_QUESTIONS:
        raise ValueError("Question count outside permitted bounds")
    result = {}
    for key, value in spec.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key):
            raise ValueError("Invalid question identifier")
        if not isinstance(value, dict):
            raise ValueError("Invalid question description")
        kind = str(value.get("type", "")).lower()
        instructions = str(value.get("instructions", "")).strip()
        if not 5 <= len(instructions) <= 1500:
            raise ValueError("Instructions missing or too long")
        if kind == "noul":
            result[key] = Noul(instructions=instructions)
        elif kind in ("choice", "score"):
            criteria = value.get("criteria")
            if kind == "choice":
                if isinstance(criteria, list):
                    criteria = {str(x): str(x) for x in criteria}
                if not isinstance(criteria, dict) or not 2 <= len(criteria) <= MAX_CRITERIA:
                    raise ValueError("Choice requires two or more bounded candidates")
                result[key] = Choice(instructions=instructions, criteria=criteria)
            else:
                if not isinstance(criteria, list) or not 2 <= len(criteria) <= MAX_CRITERIA:
                    raise ValueError("Score needs bounded criteria")
                result[key] = Score(instructions=instructions, criteria=criteria)
        else:
            raise ValueError("Unsupported JEV question type")
    return result

def atomic_write(path: Path, data: dict) -> None:
    """Write a complete JSON receipt without leaving partial files."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".jev-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def answer_data(answer: object) -> dict:
    """Normalize provider answers without inventing unsupported fields."""
    if hasattr(answer, "choice"):
        return {
            "value": answer.choice,
            "probabilities": dict(answer.probabilities),
            "confidence": getattr(answer, "confidence", None),
        }
    if hasattr(answer, "noul"):
        return {"value": float(answer.noul)}
    return {
        "value": float(answer.score),
        "confidence": getattr(answer, "confidence", None),
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", required=True)
    parser.add_argument("--questions-file", required=True)
    parser.add_argument("--out-file", required=True)
    args = parser.parse_args()

    try:
        state = load_object(args.state_file)
        spec = load_object(args.questions_file)
        questions = compile_questions(spec)
        dest = protected_path(args.out_file)
        key = KEY_PATH.read_text(encoding="ascii").strip()
        if not key.startswith("apikey_"):
            raise ValueError("No usable JEV key in protected store")
        canonical = json.dumps([state, spec], sort_keys=True, ensure_ascii=False)
        signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        lock_path = ROOT / "jev-oracle.lock"
        with open(lock_path, "a+", encoding="utf-8") as lock:
            os.chmod(lock_path, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            client = TypeSafeClient(api_key=key, model=MODEL, timeout=70)
            response = client.system_one(state=state, questions=questions, model=MODEL, timeout=70)
            usage = getattr(response, "usage", None)
            receipt = {
                "status": "connected",
                "provider": "TypeSafe JEV",
                "model": str(getattr(response, "model", MODEL)),
                "verified_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "state_questions_sha256": signature,
                "answers": {name: answer_data(item) for name, item in response.answers.items()},
                "usage": {
                    "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
                    "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
                },
            }
            atomic_write(dest, receipt)
            print(json.dumps({"status": receipt["status"], "path": str(dest),
                              "model": receipt["model"], "sha256": signature,
                              "answers": receipt["answers"]}, ensure_ascii=False))
            return 0
    except Exception as exc:
        # Error types are retained, provider exception strings are intentionally not printed.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}),
              file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())