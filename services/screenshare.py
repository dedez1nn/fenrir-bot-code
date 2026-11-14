"""Servidor web de compartilhamento de tela (WebRTC) usado pela cog ``ScreenShare``.

O vídeo **não passa pelo bot**: o navegador de quem compartilha abre uma conexão
WebRTC direta com cada espectador. O servidor aqui faz só a sinalização
(troca de offer/answer/ICE por WebSocket) e serve a página.

Acesso por links assinados (HMAC) gerados pelo bot, um por usuário e papel
(``host`` ou ``viewer``), com expiração. Sem token válido não há acesso.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from aiohttp import WSMsgType, web

log = logging.getLogger("fenrir.screenshare")

TOKEN_TTL_SECONDS = 6 * 3600
ROLE_HOST = "host"
ROLE_VIEWER = "viewer"

# Tipos de mensagem que o servidor apenas repassa entre host e espectador.
_RELAY_TYPES = {"offer", "answer", "candidate"}


# ── Tokens ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Claims:
    room_id: int
    user_id: int
    role: str
    exp: int


def _sign(secret: str, body: str) -> str:
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def make_token(secret: str, room_id: int, user_id: int, role: str,
               ttl: int = TOKEN_TTL_SECONDS, now: Optional[float] = None) -> str:
    exp = int((now if now is not None else time.time()) + ttl)
    body = f"{room_id}.{user_id}.{role}.{exp}"
    return f"{body}.{_sign(secret, body)}"


def verify_token(secret: str, token: str, now: Optional[float] = None) -> Optional[Claims]:
    parts = (token or "").split(".")
    if len(parts) != 5:
        return None
    room, user, role, exp, sig = parts
    if not hmac.compare_digest(sig, _sign(secret, ".".join(parts[:4]))):
        return None
    if role not in (ROLE_HOST, ROLE_VIEWER):
        return None
    try:
        claims = Claims(int(room), int(user), role, int(exp))
    except ValueError:
        return None
    if claims.exp < (now if now is not None else time.time()):
        return None
    return claims


# ── Salas ────────────────────────────────────────────────────────────────────

@dataclass
class Room:
    host: Optional[web.WebSocketResponse] = None
    host_uid: Optional[int] = None
    live: bool = False
    viewers: dict[str, web.WebSocketResponse] = field(default_factory=dict)


# (room_id, user_id, live) chamado quando o compartilhamento começa/termina.
HostCallback = Callable[[int, int, bool], Awaitable[None]]


class ScreenShareServer:
    def __init__(
        self,
        secret: str,
        public_url: str,
        host: str = "0.0.0.0",
        port: int = 8766,
        max_viewers: int = 8,
        ice_servers: Optional[list[dict]] = None,
        on_host_change: Optional[HostCallback] = None,
    ):
        self.secret = secret
        self.public_url = public_url.rstrip("/")
        self.host = host
        self.port = port
        self.max_viewers = max_viewers
        self.ice_servers = ice_servers or [{"urls": "stun:stun.l.google.com:19302"}]
        self.on_host_change = on_host_change
        self.rooms: dict[int, Room] = {}
        self._viewer_seq = 0
        self._runner: Optional[web.AppRunner] = None
        self.app = self._build_app()

    # -- ciclo de vida

    def _build_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/screen/ws", self._ws)
        app.router.add_get("/screen/{room_id:\\d+}", self._page)
        return app

    async def start(self) -> None:
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        await web.TCPSite(self._runner, self.host, self.port).start()
        log.info("Servidor de compartilhamento de tela em %s:%s", self.host, self.port)

    async def stop(self) -> None:
        for room in list(self.rooms.values()):
            for ws in [room.host, *room.viewers.values()]:
                if ws is not None and not ws.closed:
                    await ws.close()
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    # -- API usada pela cog

    def link(self, room_id: int, user_id: int, role: str) -> str:
        token = make_token(self.secret, room_id, user_id, role)
        return f"{self.public_url}/screen/{room_id}?t={token}"

    def is_live(self, room_id: int) -> bool:
        room = self.rooms.get(room_id)
        return bool(room and room.live)

    def host_user(self, room_id: int) -> Optional[int]:
        room = self.rooms.get(room_id)
        return room.host_uid if room and room.host is not None else None

    def viewer_count(self, room_id: int) -> int:
        room = self.rooms.get(room_id)
        return len(room.viewers) if room else 0

    async def stop_room(self, room_id: int) -> bool:
        room = self.rooms.get(room_id)
        if room is None or room.host is None or room.host.closed:
            return False
        await room.host.close()
        return True

    # -- HTTP

    async def _page(self, request: web.Request) -> web.Response:
        claims = verify_token(self.secret, request.query.get("t", ""))
        if claims is None or claims.room_id != int(request.match_info["room_id"]):
            return web.Response(status=403, text="Link inválido ou expirado. Gere outro pelo painel da call.")
        return web.Response(
            text=PAGE_HTML,
            content_type="text/html",
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )

    async def _ws(self, request: web.Request) -> web.StreamResponse:
        claims = verify_token(self.secret, request.query.get("t", ""))
        if claims is None:
            return web.Response(status=403)
        origin = request.headers.get("Origin")
        if origin and origin.split("://", 1)[-1] != request.host:
            return web.Response(status=403)

        ws = web.WebSocketResponse(heartbeat=30, max_msg_size=64 * 1024)
        await ws.prepare(request)
        room = self.rooms.setdefault(claims.room_id, Room())

        if claims.role == ROLE_HOST:
            await self._run_host(ws, room, claims)
        else:
            await self._run_viewer(ws, room, claims)

        if not room.viewers and room.host is None:
            self.rooms.pop(claims.room_id, None)
        return ws

    # -- host

    async def _run_host(self, ws: web.WebSocketResponse, room: Room, claims: Claims) -> None:
        if room.host is not None and not room.host.closed:
            await ws.send_json({"type": "error", "message": "Já existe alguém compartilhando nesta sala."})
            await ws.close()
            return
        room.host, room.host_uid, room.live = ws, claims.user_id, False
        await ws.send_json({"type": "welcome", "role": ROLE_HOST, "ice": self.ice_servers})
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                data = _parse(msg.data)
                if data is None:
                    continue
                kind = data.get("type")
                if kind == "live" and not room.live:
                    room.live = True
                    for vid, vws in list(room.viewers.items()):
                        await _safe_send(vws, {"type": "host-live"})
                        await _safe_send(ws, {"type": "viewer-joined", "id": vid})
                    await self._notify(claims.room_id, claims.user_id, True)
                elif kind in _RELAY_TYPES:
                    target = room.viewers.get(str(data.get("to")))
                    if target is not None:
                        await _safe_send(target, {"type": kind, "data": data.get("data")})
        finally:
            was_live = room.live
            room.host, room.host_uid, room.live = None, None, False
            for vws in list(room.viewers.values()):
                await _safe_send(vws, {"type": "host-left"})
            if was_live:
                await self._notify(claims.room_id, claims.user_id, False)

    # -- espectador

    async def _run_viewer(self, ws: web.WebSocketResponse, room: Room, claims: Claims) -> None:
        if len(room.viewers) >= self.max_viewers:
            await ws.send_json({"type": "error", "message": "Sala cheia de espectadores."})
            await ws.close()
            return
        self._viewer_seq += 1
        vid = f"{claims.user_id}-{self._viewer_seq}"
        room.viewers[vid] = ws
        await ws.send_json({"type": "welcome", "role": ROLE_VIEWER, "ice": self.ice_servers, "live": room.live})
        if room.live and room.host is not None:
            await _safe_send(room.host, {"type": "viewer-joined", "id": vid})
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                data = _parse(msg.data)
                if data and data.get("type") in _RELAY_TYPES and room.host is not None:
                    await _safe_send(room.host, {"type": data["type"], "from": vid, "data": data.get("data")})
        finally:
            room.viewers.pop(vid, None)
            if room.host is not None:
                await _safe_send(room.host, {"type": "viewer-left", "id": vid})

    async def _notify(self, room_id: int, user_id: int, live: bool) -> None:
        if self.on_host_change is None:
            return
        try:
            await self.on_host_change(room_id, user_id, live)
        except Exception:  # noqa: BLE001 - callback nunca pode derrubar a sinalização
            log.exception("Falha no callback de compartilhamento")


def _parse(raw: str) -> Optional[dict]:
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


async def _safe_send(ws: web.WebSocketResponse, payload: dict) -> None:
    if ws.closed:
        return
    try:
        await ws.send_json(payload)
    except (ConnectionResetError, RuntimeError):
        pass


# ── Página (cliente WebRTC) ──────────────────────────────────────────────────

PAGE_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fenrir | Compartilhamento de tela</title>
<style>
  :root { color-scheme: dark; --bg:#0f1115; --fg:#e8eaee; --muted:#8b93a1; --accent:#5865f2; }
  * { box-sizing: border-box; }
  body { margin:0; min-height:100vh; display:flex; flex-direction:column; background:var(--bg); color:var(--fg);
         font:16px/1.5 system-ui, sans-serif; }
  header { padding:12px 16px; display:flex; gap:12px; align-items:center; border-bottom:1px solid #222731; }
  header strong { flex:1; }
  #status { color:var(--muted); font-size:14px; }
  main { flex:1; display:flex; align-items:center; justify-content:center; padding:16px; }
  video { max-width:100%; max-height:calc(100vh - 100px); background:#000; border-radius:8px; display:none; }
  button { background:var(--accent); color:#fff; border:0; border-radius:8px; padding:12px 20px; font:inherit; cursor:pointer; }
  button:focus-visible { outline:2px solid #fff; outline-offset:2px; }
  button[hidden] { display:none; }
  #msg { text-align:center; color:var(--muted); }
</style>
</head>
<body>
<header><strong>🖥️ Fenrir | Tela</strong><span id="status">Conectando...</span></header>
<main>
  <div id="msg"></div>
  <video id="video" autoplay playsinline controls></video>
  <button id="start" hidden>Escolher janela ou tela para compartilhar</button>
</main>
<script>
(() => {
  const $ = id => document.getElementById(id);
  const token = new URLSearchParams(location.search).get('t') || '';
  const ws = new WebSocket((location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.host +
                           '/screen/ws?t=' + encodeURIComponent(token));
  const peers = new Map();
  let ice = [], role = null, stream = null, viewerPc = null, queue = Promise.resolve();

  const status = t => { $('status').textContent = t; };
  const say = t => { $('msg').textContent = t; };
  const send = o => ws.readyState === 1 && ws.send(JSON.stringify(o));
  const newPc = () => new RTCPeerConnection({ iceServers: ice });

  ws.onclose = () => { status('Desconectado'); if (role === 'host') stopCapture(); };
  ws.onmessage = e => { const m = JSON.parse(e.data); queue = queue.then(() => handle(m)).catch(console.error); };

  async function handle(m) {
    switch (m.type) {
      case 'error': say(m.message); status('Erro'); break;
      case 'welcome':
        role = m.role; ice = m.ice || [];
        if (role === 'host') { status('Pronto'); $('start').hidden = false; say('Clique no botão para começar.'); }
        else if (m.live) { status('Aguardando vídeo...'); }
        else { status('Ninguém compartilhando ainda'); say('Aguardando o início da transmissão...'); }
        break;
      // host
      case 'viewer-joined': await offerTo(m.id); break;
      case 'viewer-left': closePeer(m.id); break;
      case 'answer':
        if (peers.has(m.from)) await peers.get(m.from).setRemoteDescription(m.data);
        break;
      case 'candidate':
        if (role === 'host') { if (peers.has(m.from)) await peers.get(m.from).addIceCandidate(m.data); }
        else if (viewerPc) await viewerPc.addIceCandidate(m.data);
        break;
      // viewer
      case 'host-live': status('Aguardando vídeo...'); break;
      case 'host-left':
        if (viewerPc) { viewerPc.close(); viewerPc = null; }
        $('video').style.display = 'none'; $('video').srcObject = null;
        status('Transmissão encerrada'); say('O compartilhamento terminou.');
        break;
      case 'offer': await answer(m.data); break;
    }
  }

  // ----- host
  $('start').onclick = async () => {
    try {
      stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
    } catch (err) { say('Compartilhamento cancelado ou negado pelo navegador.'); return; }
    stream.getVideoTracks()[0].addEventListener('ended', () => ws.close());
    $('start').hidden = true; say('');
    const v = $('video'); v.srcObject = stream; v.muted = true; v.style.display = 'block';
    status('Ao vivo');
    send({ type: 'live' });
  };
  function stopCapture() {
    if (stream) stream.getTracks().forEach(t => t.stop());
    peers.forEach(pc => pc.close()); peers.clear();
  }
  function closePeer(id) { const pc = peers.get(id); if (pc) { pc.close(); peers.delete(id); } }
  async function offerTo(id) {
    if (!stream) return;
    const pc = newPc(); peers.set(id, pc);
    stream.getTracks().forEach(t => pc.addTrack(t, stream));
    pc.onicecandidate = e => e.candidate && send({ type: 'candidate', to: id, data: e.candidate });
    await pc.setLocalDescription(await pc.createOffer());
    send({ type: 'offer', to: id, data: pc.localDescription });
  }

  // ----- viewer
  async function answer(offer) {
    if (viewerPc) viewerPc.close();
    const pc = viewerPc = newPc();
    pc.ontrack = e => {
      const v = $('video'); v.srcObject = e.streams[0]; v.style.display = 'block';
      say(''); status('Assistindo');
    };
    pc.onicecandidate = e => e.candidate && send({ type: 'candidate', data: e.candidate });
    await pc.setRemoteDescription(offer);
    await pc.setLocalDescription(await pc.createAnswer());
    send({ type: 'answer', data: pc.localDescription });
  }
})();
</script>
</body>
</html>
"""
