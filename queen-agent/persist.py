"""
Queen Agent — Persistence module.

Cloud-backup for agent souls using Cloudflare KV.
Falls back gracefully when CF_API_TOKEN is not set (no-op).

KV Namespace: queen-souls  (ID hardcoded, same namespace for all Queen instances)

Usage:
    persist.save_souls(souls_list)   # backup after each spawn
    souls = persist.load_souls()     # restore on Queen startup

Required Railway env vars:
    CF_API_TOKEN  — Cloudflare API token with KV:Edit permission
                    (Create at: dash.cloudflare.com/profile/api-tokens)

Optional Railway env vars (defaults to the correct values):
    CF_ACCOUNT_ID    — Cloudflare account ID
    CF_KV_NAMESPACE  — KV namespace ID
"""

import json
import os

import httpx

# ── Constants ─────────────────────────────────────────────────────────────────
CF_ACCOUNT_ID  = os.getenv("CF_ACCOUNT_ID",   "eaffd2b52c95c69aaad8d859e9dcb52b")
CF_KV_NS       = os.getenv("CF_KV_NAMESPACE",  "b1d0c8cd89f944b89e6638c3861ba3e3")
CF_API_TOKEN   = os.getenv("CF_API_TOKEN",     "")          # Must be set to enable KV
KV_KEY         = "queen-souls"

_KV_BASE = (
    f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}"
    f"/storage/kv/namespaces/{CF_KV_NS}/values/{KV_KEY}"
)


# ── Public API ────────────────────────────────────────────────────────────────

def save_souls(souls: list[dict]) -> bool:
    """
    Backup souls list to Cloudflare KV.

    Args:
        souls: List of full soul dicts (as stored in registry).

    Returns:
        True on success, False if skipped (no token) or failed.
    """
    if not CF_API_TOKEN:
        return False

    # Only store fields needed to re-instantiate a VirtualAgent
    minimal = [_minimal_soul(s) for s in souls]

    try:
        r = httpx.put(
            _KV_BASE,
            content=json.dumps(minimal, ensure_ascii=False),
            headers={
                "Authorization": f"Bearer {CF_API_TOKEN}",
                "Content-Type":  "text/plain",
            },
            timeout=15.0,
        )
        return r.status_code in (200, 201)
    except Exception:
        return False


def load_souls() -> list[dict]:
    """
    Restore souls list from Cloudflare KV.

    Returns:
        List of soul dicts, or [] if not available.
    """
    if not CF_API_TOKEN:
        return []

    try:
        r = httpx.get(
            _KV_BASE,
            headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
            timeout=15.0,
        )
        if r.status_code == 200:
            data = json.loads(r.text)
            if isinstance(data, list):
                return data
    except Exception:
        pass

    return []


def is_enabled() -> bool:
    """True if CF_API_TOKEN is configured (KV persistence is active)."""
    return bool(CF_API_TOKEN)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _minimal_soul(soul: dict) -> dict:
    """
    Extract only the fields VirtualAgent.__init__ needs.
    Avoids bloating KV with unused fields.
    """
    _NEEDED = [
        "codename", "agent_id", "full_name", "specialty", "mission",
        "interests", "personality", "writing_style", "archetype",
        "domains", "llm_provider", "llm_model", "llm_env_var",
        "papers_system_prompt", "agent_url", "color_scheme",
        "research_interval",   "validation_interval",   "social_interval",
        "heartbeat_start_delay", "research_start_delay",
        "validation_start_delay", "social_start_delay",
        "jitter_research", "jitter_validation", "jitter_social",
    ]
    return {k: soul[k] for k in _NEEDED if k in soul}
