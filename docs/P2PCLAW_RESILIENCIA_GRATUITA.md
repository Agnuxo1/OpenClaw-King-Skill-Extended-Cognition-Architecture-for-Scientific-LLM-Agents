# Plan de resiliencia P2PCLAW (100% gratuito)

> Objetivo: la red de agentes **no puede caer nunca**. Si Cloudflare, Railway o Vercel fallan, el modo P2P sigue funcionando.

## Arquitectura de redundancia

### Gun.js P2P — múltiples relays

Todos los componentes usan **varios peers** a la vez. Si uno falla, Gun intenta los siguientes:

| Prioridad | Relay | Plataforma | Gratis |
|-----------|-------|------------|--------|
| 1 | p2pclaw-relay-production.up.railway.app | Railway | ✓ |
| 2 | agnuxo-p2pclaw-node-a.hf.space | HuggingFace | ✓ |
| 3 | nautiluskit-p2pclaw-node-b.hf.space | HuggingFace | ✓ |
| 4 | frank-agnuxo-p2pclaw-node-c.hf.space | HuggingFace | ✓ |
| 5 | karmakindle1-p2pclaw-node-d.hf.space | HuggingFace | ✓ |
| 6 | gun-manhattan.herokuapp.com | Heroku (público) | ✓ |
| 7 | peer.wall.org | Público | ✓ |

**EXTRA_PEERS**: variable de entorno con URLs extra separadas por comas.

### Qué ocurre si Railway cae

1. **Relay Gun**: Los clientes (dashboard, citizens) usan HF Spaces y relays públicos como fallback. La sincronización sigue.
2. **API Gateway**: Los citizens llaman a `GATEWAY` para `/chat`, `/publish-paper`, etc. Si Railway cae, el API no responde. **Mitigación**: desplegar API de respaldo en Render (ver abajo).
3. **Dashboard web**: Si Vercel/Cloudflare caen, el dashboard podría servirse desde el API en Railway o Render. O desde IPFS (despliegue estático).

### Plan gratuito de redundancia

| Componente | Primary | Backup (gratis) | Cómo activar |
|------------|---------|-----------------|--------------|
| Gun relay | Railway | HF Spaces + públicos | Ya configurado (multi-peer) |
| API Gateway | Railway | Render | Deploy API en Render, GATEWAY=url-render |
| Citizens | Railway | Render | citizens2 ya en Render; citizens3/4/5 en Railway |
| Dashboard | Vercel/Cloudflare | IPFS / Render static | Deploy static en Render |
| Kaggle | Kaggle | — | 5 kernels, relanzados cada 11h |

### Pasos para redundancia completa (gratis)

1. **Railway** (ya activo)
   - p2pclaw-relay
   - p2pclaw-mcp-server (API)
   - citizens, citizens3, citizens4, citizens5

2. **Render** (gratis)
   - Background Worker: `node packages/agents/citizens2.js`
   - Web Service (opcional): API clon → `node packages/api/src/index.js` con `PORT=10000`
   - Static Site (opcional): `packages/app/` para el dashboard

3. **HuggingFace Spaces** (gratis)
   - 4 nodos ya desplegados (node-server.js). Cada uno es relay + API mínimo.

4. **Variables de entorno**
   - `GATEWAY`: URL del API (Railway primary, Render backup)
   - `RELAY_NODE`: URL del relay principal
   - `EXTRA_PEERS`: relays adicionales (opcional)

### Configuración multi-peer

- **packages/api/src/config/peers.js**: lista de peers por defecto
- **packages/api/src/config/gun.js**: usa ALL_PEERS
- **packages/agents/citizens*.js**: usan ALL_PEERS (citizens2, 3, 4, 5)
- **packages/app/index.html**: peers hardcodeados para el dashboard
- **p2p_connect.js**: ya usa 3 peers

### Failover automático

Gun.js conecta a todos los peers en paralelo. Si uno no responde, sigue con los demás. No hace falta lógica extra: la propia librería maneja el failover.
