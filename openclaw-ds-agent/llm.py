"""
HuggingFace Inference API Client — synchronous, OpenAI-compatible.

Primary model : Qwen/Qwen2.5-72B-Instruct (powerful reasoning + math + formal proofs)
Fallback model: meta-llama/Llama-3.3-70B-Instruct
Auth          : HF_TOKEN env var (free tier)
Endpoint      : https://router.huggingface.co/hf-inference/models/{model}/v1
"""

import os
import time
import httpx

HF_TOKEN      = os.getenv("HF_TOKEN",      "")
HF_MODEL      = os.getenv("HF_MODEL",      "Qwen/Qwen2.5-72B-Instruct")
HF_MODEL_FAST = os.getenv("HF_MODEL_FAST", "meta-llama/Llama-3.3-70B-Instruct")
HF_BASE       = "https://router.huggingface.co"


def complete(
    messages: list,
    max_tokens: int = 4096,
    temperature: float = 0.72,
    fast: bool = False,
) -> str:
    """
    Call HuggingFace Serverless Inference API (synchronous).

    Uses Qwen2.5-72B for main tasks (strong math, formal proofs, category theory).
    Uses Llama-3.3-70B for fast/eval tasks.
    Retries 3 times with exponential backoff.
    """
    model = HF_MODEL_FAST if fast else HF_MODEL
    if fast:
        max_tokens = min(max_tokens, 300)

    url = f"{HF_BASE}/v1/chat/completions"  # model specified in body, not URL path
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
                # Model cold start — wait and retry
                time.sleep(25)
                continue

            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()

        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            if e.response.status_code in (401, 403):
                raise RuntimeError("HF API: auth error — check HF_TOKEN secret")
            time.sleep(10 * (attempt + 1))

        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            time.sleep(10 * (attempt + 1))

    raise RuntimeError(f"HF API (DS Theorist): all retries failed. Last: {last_error}")
