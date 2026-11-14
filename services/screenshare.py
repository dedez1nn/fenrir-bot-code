"""Servidor web do painel de telas (WebRTC) usado pela cog ``ScreenShare``.

O vídeo **não passa pelo bot**: o navegador de quem compartilha abre uma conexão
WebRTC direta com cada espectador. O servidor aqui faz só a sinalização
(offer/answer/ICE por WebSocket), mantém o estado da sala (quem está ao vivo e
quem assiste quem) e serve a página (``screenshare_page.html``).

Cada sala é um canal de voz. Vários membros podem transmitir ao mesmo tempo, e
cada espectador só conecta nas telas que abriu (poupa banda e RAM no navegador).

Acesso por link assinado (HMAC) por usuário, com expiração. O link identifica
quem é a pessoa; quem pode entrar e transmitir é decidido pelo bot, por callbacks.
Todos os ids viajam como string (ids do Discord estouram o inteiro seguro do JS).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Optional

from aiohttp import WSMsgType, web

log = logging.getLogger("fenrir.screenshare")

TOKEN_TTL_SECONDS = 6 * 3600
ROLE_MEMBER = "member"

_PAGE_PATH = Path(__file__).with_name("screenshare_page.html")
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


def make_token(secret: str, room_id: int, user_id: int, role: str = ROLE_MEMBER,
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
    if role != ROLE_MEMBER:
        return None
    try:
        claims = Claims(int(room), int(user), role, int(exp))
    except ValueError:
        return None
    if claims.exp < (now if now is not None else time.time()):
        return None
    return claims


# ── Estado das salas ─────────────────────────────────────────────────────────

@dataclass
class Conn:
    ws: web.WebSocketResponse
    uid: str
    cid: str  # id único da conexão (o mesmo usuário pode abrir duas abas)


@dataclass
class Room:
    conns: dict[str, Conn] = field(default_factory=dict)
    live: dict[str, str] = field(default_factory=dict)         # uid de quem transmite -> cid
    watches: dict[str, set[str]] = field(default_factory=dict)  # cid espectador -> uids assistidos


Participants = Callable[[int], list[dict]]          # room_id -> [{id, name, avatar}]
CanShare = Callable[[int, str], bool]               # room_id, uid -> pode transmitir?
HostCallback = Callable[[int, int, bool], Awaitable[None]]  # room_id, user_id, ao vivo?


class ScreenShareServer:
    def __init__(
        self,
        secret: str,
        public_url: str,
        host: str = "0.0.0.0",
        port: int = 8766,
        max_viewers: int = 8,
        ice_servers: Optional[list[dict]] = None,
        get_participants: Optional[Participants] = None,
        can_share: Optional[CanShare] = None,
        on_host_change: Optional[HostCallback] = None,
    ):
        self.secret = secret
        self.public_url = public_url.rstrip("/")
        self.host = host
        self.port = port
        self.max_viewers = max_viewers
        self.ice_servers = ice_servers or [{"urls": "stun:stun.l.google.com:19302"}]
        self.get_participants = get_participants or (lambda room_id: [])
        self.can_share = can_share or (lambda room_id, uid: True)
        self.on_host_change = on_host_change
        self.rooms: dict[int, Room] = {}
        self._seq = 0
        self._runner: Optional[web.AppRunner] = None
        self._page: Optional[str] = None
        self.app = self._build_app()

    # -- ciclo de vida

    def _build_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/screen/ws", self._ws)
        app.router.add_get("/screen/{room_id:\\d+}", self._page_handler)
        return app

    async def start(self) -> None:
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        await web.TCPSite(self._runner, self.host, self.port).start()
        log.info("Servidor de compartilhamento de tela em %s:%s", self.host, self.port)

    async def stop(self) -> None:
        for room in list(self.rooms.values()):
            for conn in list(room.conns.values()):
                if not conn.ws.closed:
                    await conn.ws.close()
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    # -- API usada pela cog

    def link(self, room_id: int, user_id: int) -> str:
        return f"{self.public_url}/screen/{room_id}?t={make_token(self.secret, room_id, user_id)}"

    def live_users(self, room_id: int) -> list[str]:
        room = self.rooms.get(room_id)
        return list(room.live) if room else []

    def is_live(self, room_id: int, user_id: Optional[int] = None) -> bool:
        users = self.live_users(room_id)
        return bool(users) if user_id is None else str(user_id) in users

    async def refresh(self, room_id: int) -> None:
        """Reenvia o estado (ex: alguém entrou/saiu da call, dono mudou permissão)."""
        room = self.rooms.get(room_id)
        if room is not None:
            await self._broadcast(room_id, room)

    async def stop_user(self, room_id: int, user_id: int) -> bool:
        room = self.rooms.get(room_id)
        if room is None or str(user_id) not in room.live:
            return False
        await self._stop_live(room_id, room, str(user_id))
        await self._broadcast(room_id, room)
        return True

    async def stop_room(self, room_id: int) -> int:
        room = self.rooms.get(room_id)
        if room is None:
            return 0
        users = list(room.live)
        for uid in users:
            await self._stop_live(room_id, room, uid)
        if users:
            await self._broadcast(room_id, room)
        return len(users)

    async def drop_user(self, room_id: int, user_id: int) -> None:
        """Quem saiu da call perde a transmissão e a conexão com a sala."""
        room = self.rooms.get(room_id)
        if room is None:
            return
        for conn in [c for c in room.conns.values() if c.uid == str(user_id)]:
            if not conn.ws.closed:
                await conn.ws.close()

    # -- HTTP

    def _page_html(self) -> str:
        if self._page is None:
            self._page = _PAGE_PATH.read_text(encoding="utf-8")
        return self._page

    async def _page_handler(self, request: web.Request) -> web.Response:
        claims = verify_token(self.secret, request.query.get("t", ""))
        if claims is None or claims.room_id != int(request.match_info["room_id"]):
            return web.Response(status=403, text="Link inválido ou expirado. Gere outro pelo painel da call.")
        return web.Response(
            text=self._page_html(),
            content_type="text/html",
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": (
                    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                    "img-src 'self' data: https://cdn.discordapp.com https://media.discordapp.net; "
                    "media-src 'self' blob:; connect-src 'self' ws: wss:; base-uri 'none'; form-action 'none'"
                ),
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

        room_id, uid = claims.room_id, str(claims.user_id)
        if uid not in {str(p["id"]) for p in self.get_participants(room_id)}:
            await ws.send_json({"type": "error", "message": "Entre na call para usar o painel de telas."})
            await ws.close()
            return ws

        room = self.rooms.setdefault(room_id, Room())
        self._seq += 1
        conn = Conn(ws, uid, f"{uid}-{self._seq}")
        room.conns[conn.cid] = conn
        room.watches[conn.cid] = set()
        await ws.send_json({"type": "welcome", "me": uid, "ice": self.ice_servers})
        await self._broadcast(room_id, room)
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                data = _parse(msg.data)
                if data is not None:
                    await self._handle(room_id, room, conn, data)
        finally:
            await self._leave(room_id, room, conn)
        return ws

    # -- mensagens

    async def _handle(self, room_id: int, room: Room, conn: Conn, data: dict) -> None:
        kind = data.get("type")
        if kind == "live":
            if conn.uid in room.live:
                return
            if not self.can_share(room_id, conn.uid):
                await _safe_send(conn.ws, {"type": "denied", "message": "O dono da sala não liberou o compartilhamento."})
                return
            room.live[conn.uid] = conn.cid
            await self._notify(room_id, int(conn.uid), True)
            await self._broadcast(room_id, room)
        elif kind == "stop":
            if conn.uid in room.live:
                await self._stop_live(room_id, room, conn.uid)
                await self._broadcast(room_id, room)
        elif kind == "watch":
            target = str(data.get("target", ""))
            host = room.conns.get(room.live.get(target, ""))
            watching = room.watches[conn.cid]
            if host is None or target in watching:
                return
            if sum(target in w for w in room.watches.values()) >= self.max_viewers:
                await _safe_send(conn.ws, {"type": "error", "message": "Essa tela já está com o máximo de espectadores."})
                await _safe_send(conn.ws, {"type": "watch-failed", "target": target})
                return
            watching.add(target)
            await _safe_send(host.ws, {"type": "viewer-joined", "id": conn.cid})
            await self._broadcast(room_id, room)
        elif kind == "unwatch":
            await self._unwatch(room, conn, str(data.get("target", "")))
            await self._broadcast(room_id, room)
        elif kind in _RELAY_TYPES:
            await self._relay(room, conn, kind, str(data.get("to", "")), data.get("data"))

    async def _relay(self, room: Room, conn: Conn, kind: str, to: str, payload) -> None:
        """Repassa offer/answer/candidate. ``to`` com '-' é a conexão de um espectador, senão o uid de quem transmite."""
        if "-" in to:
            # quem transmite -> espectador (só vale se o remetente transmite e o destino o assiste)
            target = room.conns.get(to)
            if target is None or room.live.get(conn.uid) != conn.cid or conn.uid not in room.watches.get(to, ()):
                return
            await _safe_send(target.ws, {"type": kind, "from": conn.uid, "data": payload})
        else:
            # espectador -> quem transmite
            host = room.conns.get(room.live.get(to, ""))
            if host is None or to not in room.watches.get(conn.cid, ()):
                return
            await _safe_send(host.ws, {"type": kind, "from": conn.cid, "data": payload})

    async def _unwatch(self, room: Room, conn: Conn, target: str) -> None:
        if target not in room.watches.get(conn.cid, set()):
            return
        room.watches[conn.cid].discard(target)
        host = room.conns.get(room.live.get(target, ""))
        if host is not None:
            await _safe_send(host.ws, {"type": "viewer-left", "id": conn.cid})

    async def _stop_live(self, room_id: int, room: Room, uid: str) -> None:
        room.live.pop(uid, None)
        for cid, watching in room.watches.items():
            if uid in watching:
                watching.discard(uid)
                other = room.conns.get(cid)
                if other is not None:
                    await _safe_send(other.ws, {"type": "host-left", "from": uid})
        await self._notify(room_id, int(uid), False)

    async def _leave(self, room_id: int, room: Room, conn: Conn) -> None:
        if room.live.get(conn.uid) == conn.cid:
            await self._stop_live(room_id, room, conn.uid)
        for target in list(room.watches.get(conn.cid, ())):
            await self._unwatch(room, conn, target)
        room.watches.pop(conn.cid, None)
        room.conns.pop(conn.cid, None)
        if room.conns:
            await self._broadcast(room_id, room)
        else:
            self.rooms.pop(room_id, None)

    # -- estado

    async def _broadcast(self, room_id: int, room: Room) -> None:
        watchers: dict[str, list[str]] = {}
        for cid, targets in room.watches.items():
            conn = room.conns.get(cid)
            for target in targets:
                if conn is not None and conn.uid not in watchers.setdefault(target, []):
                    watchers[target].append(conn.uid)
        people = [
            {
                "id": str(p["id"]),
                "name": p.get("name", ""),
                "avatar": p.get("avatar"),
                "live": str(p["id"]) in room.live,
                "viewers": watchers.get(str(p["id"]), []),
            }
            for p in self.get_participants(room_id)
        ]
        for conn in list(room.conns.values()):
            await _safe_send(conn.ws, {
                "type": "state",
                "people": people,
                "can_share": bool(self.can_share(room_id, conn.uid)),
                "max_viewers": self.max_viewers,
            })

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
