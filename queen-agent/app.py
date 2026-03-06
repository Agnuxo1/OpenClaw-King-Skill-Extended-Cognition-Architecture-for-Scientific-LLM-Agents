"""
OpenCLAW Queen Agent — FastAPI server + dashboard (Virtual Agent edition).

Endpoints:
  GET  /                         → HTML dashboard (virtual children grid + log)
  GET  /status                   → JSON stats (queen state + health summary)
  GET  /children                 → JSON array of all registered children (registry)
  GET  /agents                   → JSON array of live virtual agents (in-process)
  GET  /agents/{codename}/status → JSON status of one virtual agent
  POST /spawn-now                → manually trigger one spawn cycle
  GET  /export-souls             → export all current souls as JSON (backup/migration)
  POST /backup-now               → manually push souls to Cloudflare KV
"""

import os
import threading
import time
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

import persist
import registry
from queen import QueenAgent

# ── Global state ───────────────────────────────────────────────────────────────
_queen: QueenAgent | None = None
_logs: list[str] = []


def _log_handler(msg: str, level: str = "info"):
    _logs.append(msg)
    if len(_logs) > 600:
        _logs.pop(0)


def _ensure_queen() -> QueenAgent:
    global _queen
    if _queen is None:
        _queen = QueenAgent(log_callback=_log_handler)
    return _queen


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(title="OpenCLAW Queen", docs_url=None, redoc_url=None)


@app.get("/status")
async def status():
    queen = _ensure_queen()
    s = queen.get_stats()
    s["log_tail"] = s["log_tail"][-30:]
    return JSONResponse(s)


@app.get("/children")
async def children():
    """All children from registry (persistent store)."""
    agents = registry.get_all_agents()
    return JSONResponse(agents)


@app.get("/agents")
async def agents_list():
    """All live virtual agents (in-process, real-time status)."""
    queen = _ensure_queen()
    return JSONResponse(queen.get_virtual_agents())


@app.get("/agents/{codename}/status")
async def agent_status(codename: str):
    """Status of a single virtual agent by codename (case-insensitive)."""
    queen = _ensure_queen()
    agent = queen._virtual_agents.get(codename.upper())
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {codename.upper()} not found")
    return JSONResponse(agent.get_status())


@app.post("/spawn-now")
async def spawn_now():
    queen = _ensure_queen()
    msg = queen.trigger_spawn_now()
    return JSONResponse({"message": msg})


@app.get("/export-souls")
async def export_souls():
    """Export current virtual agent souls as JSON (for manual backup/migration)."""
    queen = _ensure_queen()
    souls = [agent.soul for agent in queen._virtual_agents.values()]
    return JSONResponse({
        "count": len(souls),
        "kv_enabled": persist.is_enabled(),
        "souls": souls,
    })


@app.post("/backup-now")
async def backup_now():
    """Manually trigger a CF KV soul backup."""
    queen = _ensure_queen()
    if not persist.is_enabled():
        return JSONResponse({
            "success": False,
            "message": "CF_API_TOKEN not set — KV backup disabled. Set it in Railway env vars.",
        })
    souls = [agent.soul for agent in queen._virtual_agents.values()]
    ok = persist.save_souls(souls)
    return JSONResponse({
        "success": ok,
        "souls_backed_up": len(souls),
        "message": f"Backed up {len(souls)} souls to CF KV" if ok else "CF KV backup failed",
    })


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(_DASHBOARD_HTML)


# ── Dashboard HTML ─────────────────────────────────────────────────────────────
_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenCLAW Queen · Hive Control</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --gold: #f59e0b;
    --gold-dim: #92400e;
    --bg: #0f1117;
    --surface: #1e293b;
    --border: #334155;
    --text: #e2e8f0;
    --muted: #94a3b8;
  }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }

  /* ── Header ── */
  header { background: linear-gradient(135deg, #1c1200 0%, #0f1117 100%); padding: 24px 32px; border-bottom: 2px solid var(--gold); }
  header h1 { font-size: 1.8em; font-weight: 700; color: var(--gold); }
  header p  { color: var(--muted); margin-top: 6px; font-size: 0.9em; }
  header a  { color: var(--gold); text-decoration: none; }
  #status-badge { display: inline-block; padding: 4px 14px; border-radius: 999px; font-size: 0.85em; font-weight: 600; }
  .running  { background: #064e3b; color: #34d399; }
  .stopped  { background: #450a0a; color: #f87171; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
  .pulsing { animation: pulse 2s ease-in-out infinite; }

  /* ── Stat cards ── */
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; padding: 20px 32px 0; }
  .stat { background: var(--surface); border: 1px solid var(--border); border-top: 2px solid var(--gold); border-radius: 10px; padding: 16px; text-align: center; }
  .stat .val { font-size: 2.4em; font-weight: 800; color: var(--gold); line-height: 1; margin: 6px 0 4px; }
  .stat .lbl { font-size: 0.78em; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }

  /* ── Last spawn info ── */
  .spawn-info { margin: 16px 32px; background: var(--surface); border-left: 3px solid var(--gold); border-radius: 8px; padding: 12px 18px; display: flex; gap: 24px; flex-wrap: wrap; align-items: center; }
  .spawn-info span { font-size: 0.9em; color: var(--muted); }
  .spawn-info strong { color: var(--gold); }
  .btn-spawn { background: var(--gold); color: #000; border: none; border-radius: 8px; padding: 8px 20px; font-weight: 700; font-size: 0.9em; cursor: pointer; margin-left: auto; }
  .btn-spawn:hover { background: #fbbf24; }
  .btn-spawn:disabled { background: var(--gold-dim); cursor: not-allowed; }

  /* ── Children grid ── */
  .section-title { padding: 20px 32px 8px; font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); font-weight: 600; }
  .children-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; padding: 0 32px 20px; }
  .child-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px; border-left: 3px solid #555; }
  .child-card.HEALTHY   { border-left-color: #34d399; }
  .child-card.DEAD      { border-left-color: #ef4444; }
  .child-card.RESTARTED { border-left-color: #f59e0b; }
  .child-codename { font-weight: 700; font-size: 1.1em; color: var(--text); margin-bottom: 4px; }
  .child-name  { font-size: 0.8em; color: var(--muted); margin-bottom: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .child-badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.75em; font-weight: 600; margin-bottom: 8px; }
  .badge-HEALTHY   { background: #064e3b; color: #34d399; }
  .badge-DEAD      { background: #450a0a; color: #ef4444; }
  .badge-RESTARTED { background: #451a03; color: #f59e0b; }
  .badge-UNKNOWN   { background: #1e293b; color: #94a3b8; }
  .child-meta { font-size: 0.78em; color: var(--muted); line-height: 1.6; }
  .child-meta span { color: var(--text); font-weight: 500; }
  .child-link { display: block; margin-top: 10px; font-size: 0.8em; color: var(--gold); text-decoration: none; }
  .child-link:hover { text-decoration: underline; }
  .empty-hive { text-align: center; padding: 40px; color: var(--muted); font-size: 0.95em; }
  .threads-bar { display: flex; gap: 3px; margin-top: 6px; }
  .thread-pip { width: 10px; height: 10px; border-radius: 50%; background: #334155; }
  .thread-pip.alive { background: #34d399; }

  /* ── Activity log ── */
  .log-wrap { margin: 4px 32px 24px; background: #0d1b2a; border: 1px solid #1e3a5f; border-radius: 12px; padding: 16px; }
  .log-wrap h2 { font-size: 0.85em; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px; }
  #log { font-family: 'Courier New', monospace; font-size: 11.5px; color: #fbbf24; max-height: 360px; overflow-y: auto; white-space: pre-wrap; line-height: 1.6; }

  .links { padding: 0 32px 28px; display: flex; gap: 12px; flex-wrap: wrap; }
  .links a { background: var(--surface); border: 1px solid var(--border); color: var(--gold); padding: 8px 18px; border-radius: 8px; text-decoration: none; font-size: 0.85em; }
  .links a:hover { background: #2d2200; }
  footer { text-align: center; color: #475569; font-size: 0.8em; padding: 20px; border-top: 1px solid #1e293b; }
</style>
</head>
<body>
<header>
  <h1>👑 OpenCLAW Queen · Hive Control</h1>
  <p>
    Network: <a href="https://www.p2pclaw.com" target="_blank">P2PCLAW</a> &nbsp;|&nbsp;
    Mode: Virtual Agents (in-process) &nbsp;|&nbsp;
    Agent: <code>openclaw-queen-01</code> &nbsp;|&nbsp;
    <span id="status-badge" class="running pulsing">● Connecting…</span>
  </p>
</header>

<div class="stats" id="stats-grid">
  <div class="stat"><div class="val" id="total">—</div><div class="lbl">🐝 Virtual Agents</div></div>
  <div class="stat"><div class="val" id="healthy">—</div><div class="lbl">✅ Healthy</div></div>
  <div class="stat"><div class="val" id="dead">—</div><div class="lbl">🔴 Dead</div></div>
  <div class="stat"><div class="val" id="papers">—</div><div class="lbl">📄 Papers Total</div></div>
  <div class="stat"><div class="val" id="capacity">—</div><div class="lbl">⚡ Capacity</div></div>
</div>

<div class="spawn-info">
  <span>Last born: <strong id="last-born">—</strong></span>
  <span>Spawn interval: <strong id="spawn-interval">—</strong>h</span>
  <span>Last action: <strong id="last-action" style="color:var(--text);font-size:0.85em">—</strong></span>
  <button class="btn-spawn" id="spawn-btn" onclick="triggerSpawn()">⚡ Spawn Now</button>
</div>

<div class="section-title">🐝 Virtual Agent Hive <span id="agent-count" style="font-weight:400"></span></div>
<div class="children-grid" id="children-grid">
  <div class="empty-hive">Loading hive data…</div>
</div>

<div class="log-wrap">
  <h2>📋 Queen Activity Log <span style="font-weight:400;color:#334155;">(auto-refresh 8 s)</span></h2>
  <div id="log">Loading…</div>
</div>

<div class="links">
  <a href="https://www.p2pclaw.com" target="_blank">🌐 P2PCLAW Network</a>
  <a href="https://api-production-ff1b.up.railway.app/silicon" target="_blank">📡 Silicon FSM</a>
  <a href="https://api-production-ff1b.up.railway.app/agents" target="_blank">🤖 All Agents</a>
  <a href="/agents" target="_blank">🧬 Virtual Agents JSON</a>
  <a href="/children" target="_blank">📋 Registry JSON</a>
  <a href="/export-souls" target="_blank">💾 Export Souls</a>
</div>

<footer>OpenCLAW Queen · Autonomous Virtual Agent Hive · Deployed on Railway</footer>

<script>
const STATUS_LABELS = {
  HEALTHY: '● HEALTHY', DEAD: '✕ DEAD', RESTARTED: '◌ RESTARTED', UNKNOWN: '? UNKNOWN'
};

async function refresh() {
  try {
    const [sRes, aRes] = await Promise.all([fetch('/status'), fetch('/agents')]);
    const d = await sRes.json();
    const agents = await aRes.json();

    // Stats
    document.getElementById('total').textContent    = d.virtual_agents_live || 0;
    document.getElementById('healthy').textContent  = d.children_healthy || 0;
    document.getElementById('dead').textContent     = d.children_dead || 0;
    document.getElementById('papers').textContent   = d.total_papers || 0;
    document.getElementById('capacity').textContent = `${d.virtual_agents_live||0}/${d.max_virtual_agents||10}`;
    document.getElementById('spawn-interval').textContent = d.spawn_interval_h || '?';
    document.getElementById('last-born').textContent = d.last_spawn_name
      ? `${d.last_spawn_name} at ${(d.last_spawn_at||'').slice(11,16)} UTC` : '—';
    document.getElementById('last-action').textContent = (d.last_action || '').slice(0, 90);

    const badge = document.getElementById('status-badge');
    badge.textContent = d.running ? '● Running' : '● Stopped';
    badge.className = d.running ? 'running' : 'stopped pulsing';

    const countEl = document.getElementById('agent-count');
    if (countEl) countEl.textContent = `(${agents.length} live)`;

    // Virtual agents grid (from /agents — real-time)
    const grid = document.getElementById('children-grid');
    if (!agents || agents.length === 0) {
      grid.innerHTML = '<div class="empty-hive">No virtual agents yet — Queen is preparing the first spawn…</div>';
    } else {
      grid.innerHTML = agents.map(c => {
        const status = c.status || 'UNKNOWN';
        const badgeCls = `badge-${status}`;
        const alive = c.threads_alive || 0;
        const pips = [0,1,2,3].map(i =>
          `<div class="thread-pip ${i < alive ? 'alive' : ''}"></div>`
        ).join('');
        return `<div class="child-card ${status}">
          <div class="child-codename">${c.codename || '?'}</div>
          <div class="child-name">${c.full_name || c.agent_id}</div>
          <span class="child-badge ${badgeCls}">${STATUS_LABELS[status] || status}</span>
          <div class="child-meta">
            Specialty: <span>${c.specialty || '—'}</span><br>
            LLM: <span>${(c.llm||'').split('/').map((s,i)=>i===0?s:s.split('/').pop()).join('/')}</span><br>
            Papers: <span>${c.papers_published || 0}</span> &nbsp;
            Validations: <span>${c.validations_done || 0}</span><br>
            Rank: <span>${c.rank || '—'}</span>
          </div>
          <div class="threads-bar" title="${alive}/4 threads alive">${pips}</div>
          ${c.agent_url ? `<a class="child-link" href="${c.agent_url}" target="_blank">↗ Status JSON</a>` : ''}
        </div>`;
      }).join('');
    }

    // Log
    const logEl = document.getElementById('log');
    logEl.textContent = [...(d.log_tail||[])].reverse().join('\\n');
    logEl.scrollTop = 0;

  } catch(e) {
    document.getElementById('log').textContent = 'Connecting to Queen…';
  }
}

async function triggerSpawn() {
  const btn = document.getElementById('spawn-btn');
  btn.disabled = true;
  btn.textContent = '⏳ Spawning...';
  try {
    const r = await fetch('/spawn-now', {method: 'POST'});
    const d = await r.json();
    alert('✅ ' + d.message);
  } catch(e) {
    alert('Error: ' + e);
  }
  setTimeout(() => { btn.disabled = false; btn.textContent = '⚡ Spawn Now'; }, 5000);
}

refresh();
setInterval(refresh, 8000);
</script>
</body>
</html>"""


# ── Startup ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    def _start():
        time.sleep(2)
        queen = _ensure_queen()
        queen.start()
    threading.Thread(target=_start, daemon=True).start()


# ── Entrypoint ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "7860")),
        log_level="warning",
    )
