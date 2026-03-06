"""
Queen Agent — Soul generation module.

Uses Groq LLM (temperature=1.0) to generate a unique soul/identity for
each new child agent. Enforces uniqueness against the existing registry.

Virtual agent edition — no HF Spaces fields.
"""

import hashlib
import json
import os
import re
from typing import Optional

import llm
import registry

QUEEN_BASE_URL = os.getenv("QUEEN_URL", "https://openclaw-queen-production.up.railway.app")

# ── Available archetypes (16 scientific domains) ──────────────────────────────
ALL_ARCHETYPES = [
    "quantum-computing",
    "neuroscience",
    "economics-game-theory",
    "climate-science",
    "materials-nanotechnology",
    "linguistics-semantics",
    "social-networks",
    "astrophysics",
    "cryptography-zkp",
    "robotics-embodied-ai",
    "philosophy-mind",
    "epidemiology",
    "bioinformatics",
    "evolutionary-algorithms",
    "energy-systems",
    "ocean-science",
]

# Archetypes already occupied by the 3 original agents
_BASELINE_USED = [
    "distributed-systems",   # openclaw-z
    "formal-mathematics",    # openclaw-ds
    "systems-programming",   # openclaw-nebula
]

# ── Available LLM options for child agents ────────────────────────────────────
_LLM_OPTIONS = """
Available LLM providers for the new agent (choose ONE):
- provider: "groq",       model: "llama-3.3-70b-versatile", llm_env_var: "GROQ_KEY"
- provider: "groq",       model: "llama-3.1-8b-instant",    llm_env_var: "GROQ_KEY"
- provider: "together",   model: "Qwen/Qwen2.5-72B-Instruct",              llm_env_var: "TOGETHER_KEY"
- provider: "together",   model: "Qwen/Qwen2.5-Coder-32B-Instruct",        llm_env_var: "TOGETHER_KEY"
- provider: "openrouter", model: "mistralai/mistral-7b-instruct",           llm_env_var: "OPENROUTER_KEY"
- provider: "openrouter", model: "anthropic/claude-3-haiku",                llm_env_var: "OPENROUTER_KEY"
- provider: "inception",  model: "mercury-2",                               llm_env_var: "INCEPTION_KEY"
"""


# ── Soul generation ───────────────────────────────────────────────────────────

def generate() -> Optional[dict]:
    """
    Generate a unique soul for a new child agent.

    Returns:
        A soul dict, or None if generation fails after all retries.
    """
    forbidden = registry.get_forbidden_names()
    used_archetypes = set(registry.get_used_archetypes()) | set(_BASELINE_USED)

    # Build archetype options — prefer unused ones
    available = [a for a in ALL_ARCHETYPES if a not in used_archetypes]
    if not available:
        available = ALL_ARCHETYPES  # all used — allow repeats with different angle

    archetype_list = "\n".join(f"  - {a}" for a in available)
    forbidden_list = ", ".join(sorted(forbidden)) if forbidden else "none yet"

    system_msg = f"""You are a creative AI soul architect for the OpenCLAW P2PCLAW research network.
Generate a unique autonomous research agent identity as a single JSON object.
This agent runs as an in-process virtual agent publishing research papers 24/7.

HARD CONSTRAINTS:
- codename MUST NOT be any of: {forbidden_list}
- archetype MUST be chosen from the available list below
- agent_id must be kebab-case ending in "-01"
- domains must be a list of [title, inv-id] pairs — exactly 18 items
- Output ONLY valid JSON — no markdown fences, no prose, no comments"""

    user_msg = f"""Create a soul for a brand-new P2PCLAW autonomous research agent.

Choose ONE archetype from this preferred list (unused archetypes):
{archetype_list}

{_LLM_OPTIONS}

The agent must be genuinely distinct from these existing agents:
- openclaw-z-01: distributed AI systems, Byzantine fault tolerance
- openclaw-ds-theorist: category theory, formal proofs, modal logic
- openclaw-nebula-01: systems programming, compilers, Rust, WebAssembly

Generate exactly this JSON schema (no extra keys, no omissions):
{{
  "codename": "WORD-DIGIT (e.g. AURORA-3, LOGOS-7, HELIX-9)",
  "full_name": "Descriptive Name Agent (4-7 words)",
  "agent_id": "kebab-case-name-01",
  "specialty": "2-4 word scientific specialty",
  "role": "Role Title (3-6 words)",
  "personality": "One sentence characterizing how this agent thinks and writes.",
  "mission": "One sentence: what this agent investigates 24/7.",
  "interests": "10-15 comma-separated research keywords",
  "domains": [
    ["Full Paper Topic Title", "inv-keyword-01"],
    ... (18 items total)
  ],
  "llm_provider": "groq|together|openrouter|inception",
  "llm_model": "exact model name from the list above",
  "llm_env_var": "env var name from the list above",
  "color_scheme": ["#hexBgHeader", "#hexAccent"],
  "writing_style": "One sentence: the stylistic signature of this agent's papers.",
  "archetype": "chosen-archetype-slug",
  "papers_system_prompt": "3-5 sentences establishing this agent persona for paper writing."
}}"""

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": user_msg},
    ]

    for attempt in range(3):
        try:
            raw = llm.complete(messages, max_tokens=2500, temperature=1.0)
            soul = _parse_soul(raw)
            if soul is None:
                continue

            # Validate uniqueness
            codename = soul.get("codename", "")
            if codename in forbidden:
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content":
                    f'The codename "{codename}" is already taken. Choose a completely different codename.'})
                continue

            # Post-process derived fields
            soul = _enrich_soul(soul)
            return soul

        except Exception as e:
            print(f"[soul] Generation attempt {attempt+1} failed: {e}")

    return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_soul(raw: str) -> Optional[dict]:
    """Extract and validate JSON from LLM output."""
    # Strip markdown fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw.strip(), flags=re.MULTILINE)
    raw = raw.strip()

    # Find the outermost JSON object
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return None

    try:
        soul = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return None

    # Validate required fields (no HF fields)
    required = ["codename", "full_name", "agent_id", "specialty", "role",
                "personality", "mission", "interests", "domains",
                "llm_provider", "llm_model", "llm_env_var",
                "color_scheme", "writing_style", "archetype",
                "papers_system_prompt"]

    for field in required:
        if field not in soul:
            print(f"[soul] Missing field: {field}")
            return None

    # Validate domains is a list of 2-element lists
    if not isinstance(soul["domains"], list) or len(soul["domains"]) < 5:
        return None

    # Normalize domains — each element must be [title, inv-id]
    cleaned = []
    for d in soul["domains"]:
        if isinstance(d, list) and len(d) >= 2:
            cleaned.append([str(d[0]), str(d[1])])
        elif isinstance(d, dict):
            title = d.get("title") or d.get("0") or str(d)
            inv   = d.get("inv_id") or d.get("1") or "inv-general"
            cleaned.append([title, inv])
    soul["domains"] = cleaned[:20]  # cap at 20

    return soul


def _enrich_soul(soul: dict) -> dict:
    """Add derived fields and timing parameters. No HF fields."""
    # Remove any HF fields the LLM may have included
    for hf_field in ("hf_account", "space_name", "hf_url"):
        soul.pop(hf_field, None)

    # Sanitize agent_id
    aid = re.sub(r"[^a-z0-9\-]", "-", soul["agent_id"].lower())
    aid = re.sub(r"-+", "-", aid).strip("-")
    soul["agent_id"] = aid

    # Sanitize codename (must be UPPERCASE)
    soul["codename"] = soul["codename"].upper()

    # Derive timing from codename hash (deterministic, avoids thundering herds)
    soul.update(derive_timing(soul["codename"]))

    # Agent URL: sub-route on Queen's Railway URL
    soul["agent_url"] = f"{QUEEN_BASE_URL}/agents/{soul['codename'].lower()}/status"

    # Announce message for heartbeat
    soul["announce_message"] = (
        f"🤖 **{soul['full_name']}** online — 24/7 autonomous researcher. "
        f"Specialty: {soul['specialty']}. Mission: {soul['mission']} "
        f"Agent ID: `{soul['agent_id']}` | Powered by {soul['llm_model']}"
    )

    # Validate color_scheme
    cs = soul.get("color_scheme", ["#0f1117", "#60a5fa"])
    if not isinstance(cs, list) or len(cs) < 2:
        cs = ["#0f1117", "#60a5fa"]
    soul["color_scheme"] = cs

    return soul


def derive_timing(codename: str) -> dict:
    """Deterministic timing parameters from codename hash."""
    h = int(hashlib.md5(codename.encode()).hexdigest(), 16)
    return {
        "research_interval":    900 + (h % 7) * 60,    # 15–22 min
        "validation_interval":  600 + (h % 5) * 60,    # 10–14 min
        "social_interval":      1800 + (h % 9) * 120,  # 30–46 min
        "heartbeat_start_delay": 3 + (h % 12),         # 3–14 s
        "research_start_delay":  45 + (h % 30),        # 45–74 s
        "validation_start_delay": 120 + (h % 60),      # 120–179 s
        "social_start_delay":    240 + (h % 120),      # 240–359 s
        "jitter_research":       60 + (h % 60),        # ±60–119 s
        "jitter_validation":     30 + (h % 60),        # ±30–89 s
        "jitter_social":         120 + (h % 240),      # ±120–359 s
    }
