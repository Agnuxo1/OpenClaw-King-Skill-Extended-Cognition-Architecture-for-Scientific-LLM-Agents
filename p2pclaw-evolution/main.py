import os
import time
import subprocess
import shutil
import random
import requests
from typing import Callable
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# LLM Provider cascade (per documentation)
# Priority 0: KoboldCPP local (when KOBOLD_URL is set)  — free, VRAM, offline
# Priority 1: Groq             — llama-3.3-70b-versatile, 7 keys
# Priority 2: Gemini 2.5 Flash — native Google API, 7 keys
# Fallback:   Inception → Sarvam → OpenRouter
# ──────────────────────────────────────────────────────────────────────────────

INCEPTION_KEY   = os.getenv("INCEPTION_API_KEY",  "sk_a75afedbd15c82dcd5a638bbe32a0b48")
OPENROUTER_KEY  = os.getenv("OPENROUTER_API_KEY", "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")
SARVAM_KEY      = os.getenv("SARVAM_API_KEY",     "sk_iie8r362_6CUMcShmSCxVddYpV2trECyf")
KOBOLD_URL      = os.getenv("KOBOLD_URL", "")

GROQ_KEYS = [
    "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",
    "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",
    "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",
    "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",
    "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",
    "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",
    "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",
]

GEMINI_KEYS = [
    "AIzaSyDSxSwWE3BUu7dLYm-TtLhul-sP-rykHug",
    "AIzaSyAWPyUrwEQRkZ6u0YFzV6glk5q8hJHm-Xw",
    "AIzaSyAGv8adg7vGJtxVIum9_Xrbd5mpidSZRGA",
    "AIzaSyAPQfwNN5vNcG9Tc48erpVh4rTKvtmBxCs",
    "AIzaSyChRw-M2QdNLosY5rqOki3YRvhH5O0eOKk",
    "AIzaSyCk68wUII4VrtcBeoAJmh8v4_zpIUJeRo8",
    "AIzaSyCjS3UD7vJg39eHGfklT_dc3Ej9an9w_Cs",
]

# Confirmed working OpenRouter free models (avoid 404):
OPENROUTER_MODELS = [
    "deepseek/deepseek-r1:free",
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
]

CYCLE_WAIT  = int(os.getenv("CYCLE_WAIT", "30"))      # seconds between generations
PLATEAU_MAX = int(os.getenv("PLATEAU_MAX", "50"))      # reset sandbox after N no-improvement gens


def _strip_md(text: str) -> str:
    """Remove leading ```python / ``` fences from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _try_inception(system: str, user: str) -> str:
    """Call Inception Labs Mercury-2."""
    r = requests.post(
        "https://api.inceptionlabs.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {INCEPTION_KEY}", "Content-Type": "application/json"},
        json={
            "model": "mercury-2",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "temperature": 0.7,
        },
        timeout=40,
    )
    r.raise_for_status()
    return _strip_md(r.json()["choices"][0]["message"]["content"])


def _try_sarvam(system: str, user: str) -> str:
    """Call Sarvam AI (sarvam-30b)."""
    r = requests.post(
        "https://api.sarvam.ai/v1/chat/completions",
        headers={"api-subscription-key": SARVAM_KEY, "Content-Type": "application/json"},
        json={
            "model": "sarvam-30b",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "temperature": 0.7,
            "max_tokens": 4096,
        },
        timeout=40,
    )
    r.raise_for_status()
    return _strip_md(r.json()["choices"][0]["message"]["content"])


def _try_openrouter(system: str, user: str) -> str:
    """Call OpenRouter — tries multiple free models until one works."""
    models = list(OPENROUTER_MODELS)
    random.shuffle(models)
    for model in models:
        try:
            print(f"DEBUG: Consultando proveedor: openrouter (Modelo: {model})...")
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://p2pclaw.com",
                    "X-Title": "P2PCLAW Evolution Engine",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                    "temperature": 0.7,
                },
                timeout=40,
            )
            if r.status_code == 404:
                print(f"ERROR: Modelo {model} no encontrado (404) — probando siguiente...")
                continue
            r.raise_for_status()
            return _strip_md(r.json()["choices"][0]["message"]["content"])
        except requests.exceptions.HTTPError as e:
            print(f"ERROR: Fallo en API openrouter ({model}): {e}")
        except Exception as e:
            print(f"ERROR: Excepción openrouter ({model}): {e}")
    raise RuntimeError("Todos los modelos de OpenRouter fallaron")


def _try_groq(system: str, user: str) -> str:
    """Call Groq — shuffles keys to avoid rate limits."""
    keys = list(GROQ_KEYS)
    random.shuffle(keys)
    for key in keys:
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                    "temperature": 0.7,
                },
                timeout=25,
            )
            if r.status_code == 429:
                continue  # rate limited, try next key
            r.raise_for_status()
            return _strip_md(r.json()["choices"][0]["message"]["content"])
        except Exception:
            pass
    raise RuntimeError("Todos los keys de Groq fallaron")


def _try_gemini(system: str, user: str) -> str:
    """Call Google Gemini direct API."""
    keys = list(GEMINI_KEYS)
    random.shuffle(keys)
    for key in keys:
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}",
                headers={"Content-Type": "application/json"},
                json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"parts": [{"text": user}]}],
                },
                timeout=25,
            )
            if r.status_code in (429, 503):
                continue
            r.raise_for_status()
            return _strip_md(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        except Exception:
            pass
    raise RuntimeError("Todos los keys de Gemini fallaron")


def _try_kobold(system: str, user: str) -> str:
    """Call local KoboldCPP (only if KOBOLD_URL is set)."""
    if not KOBOLD_URL:
        raise RuntimeError("KOBOLD_URL no configurado")
    r = requests.post(
        f"{KOBOLD_URL}/chat/completions",
        headers={"Content-Type": "application/json"},
        json={
            "model": "qwen",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "temperature": 0.8,
            "max_tokens": 12288,
        },
        timeout=120,
    )
    r.raise_for_status()
    return _strip_md(r.json()["choices"][0]["message"]["content"])


def llm_complete(system: str, user: str) -> tuple[str, str]:
    """
    Try all providers in cascade order per documentation:
      Priority 0: KoboldCPP local (if KOBOLD_URL set) — free, local GPU
      Priority 1: Groq             — llama-3.3-70b-versatile, 7 keys
      Priority 2: Gemini 2.5 Flash — native Google API, 7 keys
      Fallback:   Inception → Sarvam → OpenRouter
    Returns (content, provider_name) or raises RuntimeError if all fail.
    """
    providers = []
    if KOBOLD_URL:
        providers.append(("koboldcpp", _try_kobold))   # Priority 0: local GPU first
    providers.extend([
        ("groq",        _try_groq),       # Priority 1: Groq cluster
        ("gemini",      _try_gemini),     # Priority 2: Google Gemini 2.5 Flash
        ("inception",   _try_inception),  # Fallback A
        ("sarvam",      _try_sarvam),     # Fallback B
        ("openrouter",  _try_openrouter), # Fallback C
    ])
    for name, fn in providers:
        try:
            print(f"DEBUG: Consultando proveedor: {name}...", flush=True)
            content = fn(system, user)
            if content and len(content) > 20:
                return content, name
            print(f"DEBUG: Respuesta vacía de {name}, probando siguiente...")
        except Exception as e:
            print(f"ERROR: Fallo en API {name}: {e}")

    raise RuntimeError("CRÍTICO: Ningún proveedor LLM respondió con éxito")


# ──────────────────────────────────────────────────────────────────────────────
# Evolution Daemon
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "Eres el Agente Evolutivo P2PCLAW. Tu objetivo es optimizar y re-escribir de forma "
    "más eficiente el siguiente script Python. "
    "Mantén exactamente la misma entrada y salida. "
    "NO EXPLIQUES NADA, devuelve SOLAMENTE el texto plano del nuevo código Python sin bloques ```."
)


class EvolutionDaemon:
    def __init__(self, sandbox_dir: str, target_file: str, eval_func: Callable):
        self.sandbox_dir  = sandbox_dir
        self.target_file  = target_file
        self.eval_func    = eval_func
        self.github_user  = os.getenv("GITHUB_USER", "nautilus-p2p")

        print(f"INFO: Inicializando Daemon Sandbox en: {self.sandbox_dir}")
        os.makedirs(self.sandbox_dir, exist_ok=True)
        if not os.path.exists(os.path.join(self.sandbox_dir, ".git")):
            subprocess.run(["git", "init"],              cwd=self.sandbox_dir, capture_output=True)
            subprocess.run(["git", "add", "."],          cwd=self.sandbox_dir, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Baseline Inicial"],
                           cwd=self.sandbox_dir, capture_output=True)

    def _mutate(self) -> tuple[str, str]:
        """Read target, ask LLM to improve it. Returns (new_code, provider)."""
        target_path = os.path.join(self.sandbox_dir, self.target_file)
        with open(target_path, "r", encoding="utf-8") as f:
            current_code = f.read()
        user_prompt = f"Optimiza este código Python:\n\n{current_code}"
        return llm_complete(SYSTEM_PROMPT, user_prompt)

    def run_daemon(self):
        print("🚀 INICIANDO P2PCLAW EVOLUTION DAEMON (24/7)")

        baseline_score = self.eval_func(self.sandbox_dir)
        print(f"🧬 Baseline actual: {baseline_score:.4f} (menor = mejor)")

        generation    = 1
        plateau_count = 0

        while True:
            print(f"\n--- 🧪 Generación {generation} ---", flush=True)

            # ── Git clean ─────────────────────────────────────────────────────
            subprocess.run(["git", "reset", "--hard"], cwd=self.sandbox_dir, capture_output=True)
            subprocess.run(["git", "clean",  "-fd"],   cwd=self.sandbox_dir, capture_output=True)

            # ── Mutate ────────────────────────────────────────────────────────
            try:
                new_code, provider = self._mutate()
            except Exception as e:
                print(f"⚠️ Falló la mutación: {e} — reintentando en 10s...", flush=True)
                time.sleep(10)
                continue

            # Write mutated code
            target_path = os.path.join(self.sandbox_dir, self.target_file)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(new_code)

            # ── Evaluate ──────────────────────────────────────────────────────
            try:
                new_score = self.eval_func(self.sandbox_dir)
            except Exception as e:
                print(f"💥 Mutación con errores (por {provider}): {e}", flush=True)
                new_score = float("inf")

            # ── Darwinian selection ───────────────────────────────────────────
            if new_score < baseline_score:
                improvement = baseline_score - new_score
                print(f"✅ ¡MUTACIÓN EXITOSA! ({provider}) Mejora: -{improvement:.4f} → Score: {new_score:.4f}", flush=True)
                baseline_score = new_score
                plateau_count  = 0

                branch_name = f"evolution/gen-{generation}-{provider}"
                subprocess.run(["git", "checkout", "-b", branch_name], cwd=self.sandbox_dir, capture_output=True)
                subprocess.run(["git", "add", "."],                     cwd=self.sandbox_dir, capture_output=True)
                msg = f"[AUTO] Gen {generation} ({provider}): Score {new_score:.4f}"
                subprocess.run(["git", "commit", "-m", msg],            cwd=self.sandbox_dir, capture_output=True)
                # Merge back to main
                subprocess.run(["git", "checkout", "main"],  cwd=self.sandbox_dir, capture_output=True)
                subprocess.run(["git", "merge",  branch_name], cwd=self.sandbox_dir, capture_output=True)

            else:
                print(f"❌ Descartado ({provider}). Score: {new_score:.4f}.", flush=True)
                plateau_count += 1

            # ── Plateau detection → reset sandbox ────────────────────────────
            if plateau_count >= PLATEAU_MAX:
                print(f"🔄 Plateau detectado ({plateau_count} gens sin mejora) — reiniciando sandbox con objetivo más difícil...", flush=True)
                _reset_sandbox(self.sandbox_dir, self.target_file)
                baseline_score = self.eval_func(self.sandbox_dir)
                plateau_count  = 0
                print(f"🧬 Nuevo baseline: {baseline_score:.4f}", flush=True)

            generation += 1
            print(f"💤 Esperando ciclo ({CYCLE_WAIT}s)...", flush=True)
            time.sleep(CYCLE_WAIT)


# ──────────────────────────────────────────────────────────────────────────────
# Sandbox targets (escalating difficulty)
# ──────────────────────────────────────────────────────────────────────────────

_TARGET_VARIANTS = [
    # Level 0: Fibonacci(30) — slow recursive
    """\
def slow_fibonacci(n):
    if n <= 1:
        return n
    return slow_fibonacci(n-1) + slow_fibonacci(n-2)

def main():
    result = slow_fibonacci(30)
    with open("output.txt", "w") as f:
        f.write(str(result))

if __name__ == "__main__":
    main()
""",
    # Level 1: Fibonacci(35) — slower
    """\
def slow_fibonacci(n):
    if n <= 1:
        return n
    return slow_fibonacci(n-1) + slow_fibonacci(n-2)

def main():
    result = slow_fibonacci(35)
    with open("output.txt", "w") as f:
        f.write(str(result))

if __name__ == "__main__":
    main()
""",
    # Level 2: Sieve of Eratosthenes (naive) — count primes up to 100k
    """\
def count_primes(n):
    primes = []
    for i in range(2, n):
        is_prime = True
        for j in range(2, i):
            if i % j == 0:
                is_prime = False
                break
        if is_prime:
            primes.append(i)
    return len(primes)

def main():
    result = count_primes(10000)
    with open("output.txt", "w") as f:
        f.write(str(result))

if __name__ == "__main__":
    main()
""",
]

_EXPECTED_OUTPUTS = ["832040", "9227465", "1229"]
_current_level = [0]


def _reset_sandbox(sandbox_dir: str, target_file: str):
    """Escalate to next difficulty level or cycle back."""
    _current_level[0] = (_current_level[0] + 1) % len(_TARGET_VARIANTS)
    level = _current_level[0]
    target_path = os.path.join(sandbox_dir, target_file)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(_TARGET_VARIANTS[level])
    # Re-commit the new baseline
    subprocess.run(["git", "reset", "--hard"],                        cwd=sandbox_dir, capture_output=True)
    subprocess.run(["git", "add",   target_file],                     cwd=sandbox_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", f"New target level {level}"], cwd=sandbox_dir, capture_output=True)
    print(f"🎯 Nuevo objetivo nivel {level} cargado", flush=True)


def get_evaluator(target_script_name: str):
    """Time-based evaluator. Validates output correctness before scoring."""
    def evaluator(sandbox_dir: str) -> float:
        import time as _time
        start = _time.time()
        try:
            res = subprocess.run(
                ["python", target_script_name],
                cwd=sandbox_dir, capture_output=True, text=True, timeout=10,
            )
            elapsed = _time.time() - start
        except subprocess.TimeoutExpired:
            raise RuntimeError("Script excedió timeout (10s)")
        if res.returncode != 0:
            raise RuntimeError(f"Script falló:\n{res.stderr[:300]}")
        output_file = os.path.join(sandbox_dir, "output.txt")
        if not os.path.exists(output_file):
            raise RuntimeError("No se generó output.txt")
        with open(output_file) as f:
            actual = f.read().strip()
        expected = _EXPECTED_OUTPUTS[_current_level[0]]
        if actual != expected:
            raise RuntimeError(f"Corrupción de lógica: got '{actual}', expected '{expected}'")
        return elapsed
    return evaluator


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    base_dir    = os.path.dirname(os.path.abspath(__file__))
    sandbox_dir = os.path.join(base_dir, "daemon_sandbox")

    os.makedirs(sandbox_dir, exist_ok=True)

    target_path = os.path.join(sandbox_dir, "target.py")
    if not os.path.exists(target_path):
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(_TARGET_VARIANTS[0])

    print("=== P2PCLAW EVOLUTION DAEMON ===")
    print(f"Sandbox:    {sandbox_dir}")
    print(f"Cycle wait: {CYCLE_WAIT}s | Plateau reset after: {PLATEAU_MAX} gens")
    kobold_status = f"koboldcpp({KOBOLD_URL}) → " if KOBOLD_URL else ""
    print(f"Providers:  {kobold_status}groq → gemini-2.5-flash → inception → sarvam → openrouter")

    daemon = EvolutionDaemon(sandbox_dir, "target.py", get_evaluator("target.py"))
    daemon.run_daemon()
