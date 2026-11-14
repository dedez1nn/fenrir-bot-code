"""Compartilhamento de tela nas calls temporárias (painel de controle da sala).

Discord não deixa bot transmitir vídeo, então o bot sobe uma sala web WebRTC
(``services/screenshare.py``) e entrega links assinados por usuário. Os botões
ficam no painel criado por ``cria_canal.VoiceControlView``.

Variáveis de ambiente:
- ``SCREENSHARE_PUBLIC_URL``: URL pública do servidor (ex: https://tela.exemplo.com).
  Padrão: ``http://localhost:<porta>`` (só funciona na própria máquina).
- ``SCREENSHARE_HOST`` / ``SCREENSHARE_PORT``: bind (padrão 0.0.0.0:8766).
- ``SCREENSHARE_SECRET``: segredo dos links (padrão: ``JWT_SECRET``, senão aleatório por execução).
- ``SCREENSHARE_MAX_VIEWERS``: máximo de espectadores simultâneos (padrão 8).
- ``SCREENSHARE_TURN_URL`` / ``_USER`` / ``_PASS``: servidor TURN opcional para redes restritivas.
"""
import logging
import os
import secrets
from typing import Optional

import discord
from discord.ext import commands

from services.screenshare import ROLE_HOST, ROLE_VIEWER, ScreenShareServer

log = logging.getLogger("fenrir.screenshare")


class ScreenShare(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.server: Optional[ScreenShareServer] = None
        # Por sala (id do canal de voz): se membros além do dono podem compartilhar.
        self._allow_members: dict[int, bool] = {}

    async def cog_load(self) -> None:
        port = int(os.getenv("SCREENSHARE_PORT", "8766"))
        public_url = os.getenv("SCREENSHARE_PUBLIC_URL") or f"http://localhost:{port}"
        secret = os.getenv("SCREENSHARE_SECRET") or os.getenv("JWT_SECRET") or secrets.token_hex(32)

        ice = [{"urls": "stun:stun.l.google.com:19302"}]
        turn_url = os.getenv("SCREENSHARE_TURN_URL")
        if turn_url:
            ice.append({
                "urls": turn_url,
                "username": os.getenv("SCREENSHARE_TURN_USER", ""),
                "credential": os.getenv("SCREENSHARE_TURN_PASS", ""),
            })

        server = ScreenShareServer(
            secret=secret,
            public_url=public_url,
            host=os.getenv("SCREENSHARE_HOST", "0.0.0.0"),
            port=port,
            max_viewers=int(os.getenv("SCREENSHARE_MAX_VIEWERS", "8")),
            ice_servers=ice,
            on_host_change=self._on_host_change,
        )
        try:
            await server.start()
        except OSError as exc:
            log.warning("Compartilhamento de tela desativado (porta %s indisponível): %s", port, exc)
            return
        self.server = server

    async def cog_unload(self) -> None:
        if self.server is not None:
            await self.server.stop()
            self.server = None

    # -- consultas usadas pelo painel

    @property
    def available(self) -> bool:
        return self.server is not None

    def allow_members(self, channel_id: int) -> bool:
        return self._allow_members.get(channel_id, False)

    def set_allow_members(self, channel_id: int, value: bool) -> None:
        self._allow_members[channel_id] = value

    def can_share(self, member, owner, channel_id: int) -> bool:
        return member == owner or self.allow_members(channel_id)

    def link(self, channel_id: int, user_id: int, role: str) -> str:
        assert self.server is not None
        return self.server.link(channel_id, user_id, role)

    # -- eventos

    async def _on_host_change(self, room_id: int, user_id: int, live: bool) -> None:
        channel = self.bot.get_channel(room_id)
        if channel is None:
            return
        if live:
            text = (f"🖥️ <@{user_id}> começou a compartilhar a tela. "
                    f"Use **👁️ Assistir** no painel para ver.")
        else:
            text = f"⏹️ <@{user_id}> encerrou o compartilhamento de tela."
        try:
            await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Quem compartilha e sai da call tem o compartilhamento encerrado."""
        if self.server is None or before.channel is None or before.channel == after.channel:
            return
        if self.server.host_user(before.channel.id) == member.id:
            await self.server.stop_room(before.channel.id)


async def setup(bot):
    await bot.add_cog(ScreenShare(bot))
