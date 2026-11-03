#!/usr/bin/env python3
"""Idempotent, evidence-gated GitHub repository provisioner for Server-IA.

Copyright (c) 2026 Francisco Angulo de Lafuente.
ORCID: https://orcid.org/0009-0001-1634-7063
SPDX-License-Identifier: MIT

Only the verified Agnuxo1 account and api.github.com are supported.
A newly created contest repository is PRIVATE by default so publication
cannot accidentally breach an ongoing competition's disclosure restrictions.
Separate, source-backed release review is required before making it public.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any
import urllib.error
import urllib.request

OWNER = "Agnuxo1"
API = "https://api.github.com"
KEY = Path("/home/ai/.openclaw/github.key")
STATE = Path("/srv/openclaw/competition-state").resolve()
RECEIPTS = STATE / "github-provision-receipts"
REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")
AUTHOR = "Francisco Angulo de Lafuente"

def private_file(path: str) -> Path:
    """Resolve a project-evidence path confined to the server's state tree."""
    p = Path(path).expanduser().resolve()
    if p != STATE and STATE not in p.parents:
        raise ValueError("Evidence must reside inside competition-state")
    if not p.is_file() or p.stat().st_size > 100000:
        raise ValueError("Missing or oversized evidence document")
    return p

def validate_evidence(raw_path: str, *, making_public: bool = False) -> dict[str, Any]:
    """Require positive official-source and license review, not heuristic leads."""
    evidence = json.loads(private_file(raw_path).read_text(encoding="utf-8"))
    if not isinstance(evidence, dict):
        raise ValueError("Evidence must be a JSON object")
    mandatory = ("rules_verified", "eligible_confirmed", "submission_rules_reviewed")
    if not all(evidence.get(name) is True for name in mandatory):
        raise ValueError("Official rules, eligibility and submission review required")
    official_url = evidence.get("official_url")
    if not isinstance(official_url, str) or not official_url.startswith("https://"):
        raise ValueError("An official HTTPS contest URL is required")
    if making_public and evidence.get("public_release_permitted") is not True:
        raise ValueError("Public release is forbidden without an explicit license gate")
    return evidence

def call_github(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    """Call only the official GitHub API with owner-local credentials."""
    if not path.startswith("/repos/" + OWNER + "/") and path != "/user/repos":
        raise ValueError("Unsupported repository endpoint")
    token = KEY.read_text(encoding="ascii").strip()
    if not (token.startswith("github_pat_") or token.startswith("ghp_")):
        raise ValueError("GitHub authentication not configured")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        API + path, method=method, data=data,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Server-IA-Evidence-Gated-Repo-Manager",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.load(response)
            if not isinstance(result, dict):
                raise ValueError("Unexpected GitHub response")
            return response.status, result
    except urllib.error.HTTPError as exc:
        # GitHub error bodies sometimes echo private request details.
        # Do not log them or any authentication header.
        if exc.code == 404 and method == "GET":
            return 404, {}
        raise RuntimeError("GitHub API HTTP " + str(exc.code)) from None

def existing_repository(name: str) -> dict | None:
    """Check for a canonical repository without creating anything."""
    status, data = call_github("GET", "/repos/" + OWNER + "/" + name)
    if status == 404:
        return None
    owner = data.get("owner", {}).get("login", "")
    if owner.lower() != OWNER.lower():
        raise ValueError("Unexpected repository owner")
    return {
        "full_name": data.get("full_name"),
        "url": data.get("html_url"),
        "private": bool(data.get("private")),
        "created_new": False,
        "push_permission": bool(data.get("permissions", {}).get("push")),
    }

def atomic_receipt(name: str, payload: dict) -> str:
    """Save an owner-only immutable operation receipt to the server's data disk."""
    RECEIPTS.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = RECEIPTS / (name + ".json")
    fd, temp = tempfile.mkstemp(dir=RECEIPTS, prefix=".repo-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return str(path)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-name", required=True)
    parser.add_argument("--ensure", action="store_true",
                        help="Create a missing repository after official evidence validation")
    parser.add_argument("--evidence-file",
                        help="Required for --ensure, with official rules and eligibility gates")
    parser.add_argument("--description",
                        default="Scientific competition research project by Francisco Angulo de Lafuente")
    parser.add_argument("--public", action="store_true",
                        help="Create publicly only when evidence explicitly permits disclosure")
    args = parser.parse_args()
    try:
        name = args.repo_name
        if not REPO_RE.fullmatch(name) or ".." in name or name.endswith(".git"):
            raise ValueError("Invalid repository name")
        existing = existing_repository(name)
        if existing is not None:
            result = existing
        elif not args.ensure:
            result = {"full_name": OWNER + "/" + name,
                      "exists": False, "created_new": False}
        else:
            if not args.evidence_file:
                raise ValueError("Creating a repository requires an evidence-file")
            evidence = validate_evidence(args.evidence_file, making_public=args.public)
            fields = {
                "name": name,
                "description": args.description[:300],
                "private": not args.public,
                "auto_init": True,
                "license_template": "mit",
                "has_issues": True,
                "has_wiki": False,
            }
            status, data = call_github("POST", "/user/repos", fields)
            if status != 201 or data.get("full_name", "").lower() != (
                    OWNER + "/" + name).lower():
                raise ValueError("GitHub did not confirm a newly created repository")
            result = {
                "full_name": data["full_name"],
                "url": data.get("html_url"),
                "private": bool(data.get("private")),
                "created_new": True,
                "official_contest": evidence["official_url"],
                "push_permission": bool(data.get("permissions", {}).get("push")),
            }
        receipt = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "author": AUTHOR,
            "orcid": "https://orcid.org/0009-0001-1634-7063",
            "license": "MIT",
            "action": "ensure" if args.ensure else "check",
            "repository": result,
        }
        path = atomic_receipt(name, receipt)
        print(json.dumps({"status": "verified", "receipt": path,
                          "repository": result}, ensure_ascii=False))
        return 0
    except Exception as exc:
        # Only stable, local error names; no provider response body or token.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "message": str(exc)[:140] if isinstance(exc, ValueError)
                          else "Operation failed"}), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())