#!/usr/bin/env python3
"""Git HTTPS credential helper restricted to github.com and the Agnuxo1 owner.

Copyright (c) 2026 Francisco Angulo de Lafuente.
ORCID: https://orcid.org/0009-0001-1634-7063
MIT License. Do not publish credentials or use this helper on untrusted hosts.

The helper sends a key only to Git credential negotiation over the trusted
github.com HTTPS origin. It never stores credentials or prints them to logs.
"""
from __future__ import annotations
from pathlib import Path
import sys

KEY = Path("/home/ai/.openclaw/github.key")
ALLOWED_HOST = "github.com"

def main() -> int:
    """Respond to Git's credential protocol for an explicitly allowed origin."""
    if len(sys.argv) != 2 or sys.argv[1] != "get":
        return 0
    attributes: dict[str, str] = {}
    for line in sys.stdin:
        line = line.strip()
        if not line:
            break
        if "=" in line:
            key, value = line.split("=", 1)
            attributes[key] = value
    protocol = attributes.get("protocol", "")
    host = attributes.get("host", "").lower()
    path = attributes.get("path", "")
    if protocol != "https" or host != ALLOWED_HOST:
        return 0
    if path and not (path.startswith("Agnuxo1/") or path.startswith("agnuxo1/")):
        return 0
    try:
        token = KEY.read_text(encoding="ascii").strip()
    except OSError:
        return 1
    if not (token.startswith("github_pat_") or token.startswith("ghp_")):
        return 1
    sys.stdout.write("username=x-access-token\npassword=" + token + "\n\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())