"""
LLM Client — dual-provider, synchronous, OpenAI-compatible.

Primary  : Together AI — Qwen/Qwen2.5-Coder-32B-Instruct
           Set TOGETHER_KEY env var in HF Space secrets.
Fallback : HF Router  — router.huggingface.co (replaces deprecated
           api-inference.huggingface.co which returned HTTP 410).
           Auth: HF_TOKEN env var (free tier).

Qwen2.5-Coder-32B achieves top scores on HumanEval, SWE-bench, BigCodeBench.
Perfect for papers with real code, Big-O analysis, and benchmark tables.
"""

import os
import time
import httpx

# ── Together AI (primary) ───────────────────────────────────────────────────
TOGETHER_KEY    = os.getenv("TOGETHER_KEY", "")
TOGETHER_BASE   = "https://api.together.xyz/v1"
TOGETHER_MODEL  = "Qwen/Qwen2.5-Coder-32B-Instruct"
TOGETHER_FAST   = "Qwen/Qwen2.5-72B-Instruct"

# ── HF Router (fallback — replaces deprecated api-inference.huggingface.co) ──
HF_TOKEN        = os.getenv("HF_TOKEN", "")
HF_BASE         = "https://router.huggingface.co"   # model in body, not path
HF_MODEL        = os.getenv("HF_MODEL",      "Qwen/Qwen2.5-Coder-32B-Instruct")
HF_MODEL_FAST   = os.getenv("HF_MODEL_FAST", "Qwen/Qwen2.5-72B-Instruct")


def _call_together(messages: list, max_tokens: int, temperature: float, fast: bool) -> str:
    """Call Together AI OpenAI-compatible endpoint."""
    model = TOGETHER_FAST if fast else TOGETHER_MODEL
    if fast:
        max_tokens = min(max_tokens, 300)

    url = f"{TOGETHER_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {TOGETHER_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       model,
        "messages":    messages,
        "max_tokens":  max_tokens,
        "temperature": temperature,
        "stream":      False,
    }

    last_error = "no attempt made"
    for attempt in range(3):
        try:
            r = httpx.post(url, headers=headers, json=payload, timeout=120.0)

            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                last_error = f"429 rate-limited (waiting {wait}s)"
                time.sleep(wait)
                continue

            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()

        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            if e.response.status_code in (401, 403):
                raise RuntimeError("Together AI: auth error — check TOGETHER_KEY")
            time.sleep(10 * (attempt + 1))

        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            time.sleep(10 * (attempt + 1))

    raise RuntimeError(f"Together AI: all retries failed. Last: {last_error}")


def _call_hf_router(messages: list, max_tokens: int, temperature: float, fast: bool) -> str:
    """Call HF Router (updated endpoint — replaces deprecated api-inference.huggingface.co)."""
    model = HF_MODEL_FAST if fast else HF_MODEL
    if fast:
        max_tokens = min(max_tokens, 300)

    url = f"{HF_BASE}/v1/chat/completions"  # model in body, not URL path
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       model,
        "messages":    messages,
        "max_tokens":  max_tokens,
        "temperature": temperature,
        "stream":      False,
    }

    # Cap tokens to avoid 504 Gateway Timeout on HF free tier
    payload["max_tokens"] = min(payload["max_tokens"], 4096)

    last_error = "no attempt made"
    for attempt in range(3):
        try:
            r = httpx.post(url, headers=headers, json=payload, timeout=240.0)

            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                last_error = f"429 rate-limited (waiting {wait}s)"
                time.sleep(wait)
                continue

            if r.status_code == 503:
                time.sleep(25)
                continue

            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()

        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            if e.response.status_code in (401, 403):
                raise RuntimeError("HF Router: auth error — check HF_TOKEN")
            time.sleep(10 * (attempt + 1))

        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            time.sleep(10 * (attempt + 1))

    raise RuntimeError(f"HF Router (Nebula): all retries failed. Last: {last_error}")


def complete(
    messages: list,
    max_tokens: int = 4096,
    temperature: float = 0.65,
    fast: bool = False,
) -> str:
    """
    Call LLM API with automatic fallback chain:
      1. Together AI (if TOGETHER_KEY is set) — best quality + reliability
      2. HF Router (router.huggingface.co) — free fallback

    Raises RuntimeError only if ALL providers fail.
    """
    # Try Together AI first if key is available
    if TOGETHER_KEY:
        try:
            return _call_together(messages, max_tokens, temperature, fast)
        except RuntimeError as e:
            print(f"[LLM] Together AI failed, trying HF Router: {e}")

    # Fall back to HF Router
    if HF_TOKEN:
        return _call_hf_router(messages, max_tokens, temperature, fast)

    raise RuntimeError(
        "LLM: no provider available — set TOGETHER_KEY or HF_TOKEN in HF Space secrets"
    )
