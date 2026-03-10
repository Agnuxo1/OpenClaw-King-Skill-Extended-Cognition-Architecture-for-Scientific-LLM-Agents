"""
P2PCLAW API Client — verbatim copy from openclaw-z-agent.
Used by queen.py for network communication (heartbeat, chat, registration).

Base: https://api-production-ff1b.up.railway.app
"""

import os
import httpx
from typing import Optional


API_BASE = os.getenv("P2P_API", "https://api-production-ff1b.up.railway.app")
_TIMEOUT = 30.0


class P2PClient:
    def __init__(self, agent_id: str, agent_name: str):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self._http = httpx.Client(
            timeout=_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": f"OpenCLAW-Queen/{agent_id}"},
        )

    def register(self, interests: str = "multi-agent systems, hive coordination") -> dict:
        return self._post("/quick-join", {
            "agentId": self.agent_id,
            "name": self.agent_name,
            "type": "ai-agent",
            "role": "spawner",
            "interests": interests,
            "capabilities": ["spawn", "monitor", "coordinate"],
        })

    def chat(self, message: str) -> dict:
        return self._post("/chat", {
            "message": message,
            "sender": self.agent_id,
        })

    def get_agents(self) -> list:
        r = self._http.get(f"{API_BASE}/agents", timeout=15.0)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict, timeout: float = _TIMEOUT) -> dict:
        r = self._http.post(f"{API_BASE}{path}", json=body, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def close(self):
        self._http.close()
