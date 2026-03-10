"""
Queen Agent — LLM client.

7-tier fallback chain (most reliable → last resort):
  1. Groq        — llama-3.3-70b-versatile (primary, fastest)
  2. Inception   — mercury-2
  3. OpenRouter  — meta-llama/llama-3.3-70b-instruct
  4. Sarvam      — sarvam-105b (single key or env var)
  5. HF          — Qwen2.5-72B-Instruct (free, slow)
  6. KoboldCPP   — local Qwen GGUF (only if KOBOLD_URL set)
"""

import itertools
import os
import time
import httpx
from typing import Optional

# ── Groq (primary) ────────────────────────────────────────────────────────────
_GROQ_KEY   = os.getenv("GROQ_KEY", "")
_GROQ_BASE  = "https://api.groq.com/openai/v1"
_GROQ_MODEL = "llama-3.3-70b-versatile"

# ── Inception Mercury-2 ────────────────────────────────────────────────────────
_INC_KEY   = os.getenv("INCEPTION_KEY", "sk_a75afedbd15c82dcd5a638bbe32a0b48")
_INC_BASE  = "https://api.inceptionlabs.ai/v1"
_INC_MODEL = "mercury-2"

# ── OpenRouter ─────────────────────────────────────────────────────────────────
_OR_KEY   = os.getenv("OPENROUTER_KEY", "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")
_OR_BASE  = "https://openrouter.ai/api/v1"
_OR_MODEL = "meta-llama/llama-3.3-70b-instruct"

# ── Sarvam AI (single key, or override via env) ────────────────────────────────
_SARVAM_BASE  = "https://api.sarvam.ai/v1"
_SARVAM_MODEL = "sarvam-105b"
_SARVAM_KEYS: list = [k for k in [
    os.getenv("SARVAM_KEY_1", "sk_iie8r362_6CUMcShmSCxVddYpV2trECyf"),
    os.getenv("SARVAM_KEY_2", ""),
    os.getenv("SARVAM_KEY_3", ""),
    os.getenv("SARVAM_KEY_4", ""),
] if k]
_sarvam_cycle = itertools.cycle(_SARVAM_KEYS) if _SARVAM_KEYS else iter([])

# ── HF Inference (free, last resort cloud) ─────────────────────────────────────
_HF_TOKEN = os.getenv("HF_TOKEN_AGNUXO", "")
_HF_URL   = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-72B-Instruct/v1/chat/completions"

# ── KoboldCPP local (only if KOBOLD_URL is set) ────────────────────────────────
_KOBOLD_URL = os.getenv("KOBOLD_URL", "")  # e.g. http://localhost:5001/v1


# ── Providers ─────────────────────────────────────────────────────────────────

def _try_groq(messages: list, max_tokens: int, temperature: float) -> Optional[str]:
    if not _GROQ_KEY:
        return None
    try:
        r = httpx.post(
            f"{_GROQ_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {_GROQ_KEY}", "Content-Type": "application/json"},
            json={"model": _GROQ_MODEL, "messages": messages,
                  "max_tokens": max_tokens, "temperature": temperature},
            timeout=60.0,
        )
        if r.status_code == 429:
            time.sleep(30)
            return None
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def _try_inception(messages: list, max_tokens: int, temperature: float) -> Optional[str]:
    if not _INC_KEY:
        return None
    try:
        r = httpx.post(
            f"{_INC_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {_INC_KEY}", "Content-Type": "application/json"},
            json={"model": _INC_MODEL, "messages": messages,
                  "max_tokens": max_tokens, "temperature": temperature},
            timeout=60.0,
        )
        if r.status_code == 429:
            return None
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def _try_openrouter(messages: list, max_tokens: int, temperature: float) -> Optional[str]:
    if not _OR_KEY:
        return None
    try:
        r = httpx.post(
            f"{_OR_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {_OR_KEY}", "Content-Type": "application/json",
                     "X-Title": "OpenCLAW Queen"},
            json={"model": _OR_MODEL, "messages": messages,
                  "max_tokens": max_tokens, "temperature": temperature},
            timeout=90.0,
        )
        if r.status_code == 429:
            return None
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def _try_sarvam(messages: list, max_tokens: int, temperature: float) -> Optional[str]:
    """Try Sarvam AI, rotating through available keys on rate limit."""
    if not _SARVAM_KEYS:
        return None
    for _ in range(len(_SARVAM_KEYS)):
        key = next(_sarvam_cycle)
        if not key:
            continue
        try:
            r = httpx.post(
                f"{_SARVAM_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": _SARVAM_MODEL, "messages": messages,
                      "max_tokens": max_tokens, "temperature": temperature},
                timeout=15.0,
            )
            if r.status_code == 429:
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            continue
    return None


def _try_hf(messages: list, max_tokens: int, temperature: float) -> Optional[str]:
    if not _HF_TOKEN:
        return None
    try:
        r = httpx.post(
            _HF_URL,
            headers={"Authorization": f"Bearer {_HF_TOKEN}", "Content-Type": "application/json"},
            json={"model": "Qwen/Qwen2.5-72B-Instruct", "messages": messages,
                  "max_tokens": max_tokens, "temperature": min(temperature, 0.99),
                  "stream": False},
            timeout=120.0,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def _try_kobold(messages: list, max_tokens: int, temperature: float) -> Optional[str]:
    """Try local KoboldCPP (OpenAI-compatible API). Only if KOBOLD_URL is set."""
    if not _KOBOLD_URL:
        return None
    try:
        r = httpx.post(
            f"{_KOBOLD_URL}/chat/completions",
            headers={"Authorization": "Bearer sk-local-dummy", "Content-Type": "application/json"},
            json={"model": "kobold", "messages": messages,
                  "max_tokens": max_tokens, "temperature": temperature},
            timeout=180.0,  # local inference can be slow
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def complete(
    messages:    list,
    max_tokens:  int   = 2000,
    temperature: float = 0.9,
) -> str:
    """
    Call LLM with 7-tier fallback chain.
    Raises RuntimeError if all providers fail.
    """
    for attempt in range(2):  # retry once on rate limits
        result = _try_groq(messages, max_tokens, temperature)
        if result:
            return result

        result = _try_inception(messages, max_tokens, temperature)
        if result:
            return result

        result = _try_openrouter(messages, max_tokens, temperature)
        if result:
            return result

        result = _try_sarvam(messages, max_tokens, temperature)
        if result:
            return result

        if attempt == 0:
            time.sleep(15)  # brief wait before second pass

    # Last resort cloud
    result = _try_hf(messages, max_tokens, temperature)
    if result:
        return result

    # Last resort local (only if KOBOLD_URL configured)
    result = _try_kobold(messages, max_tokens, temperature)
    if result:
        return result

    raise RuntimeError(
        "All LLM providers failed. "
        "Check GROQ_KEY, INCEPTION_KEY, OPENROUTER_KEY, SARVAM_KEY_1, HF_TOKEN_AGNUXO."
    )
