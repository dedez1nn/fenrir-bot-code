"""Compartilhamento de tela nas calls temporárias (painel de controle da sala).

Discord não deixa bot transmitir vídeo, então o bot sobe uma sala web WebRTC
(``services/screenshare.py``) e entrega links assinados por usuário. Os botões
ficam no painel criado por ``cria_canal.VoiceControlView``.

Variáveis de ambiente:
- ``SCREENSHARE_PUBLIC_URL``: URL pública do servidor (ex: https://tela.exemplo.com).
  Padrão: ``http://localhost:<porta>`` (só funciona na própria máquina).
- ``SCREENSHARE_HOST`` / ``SCREENSHARE_PORT``: bind (padrão 0.0.0.0:8766).
- ``SCREENSHARE_SECRET``: segredo dos links (padrão: ``JWT_SECRET``, senão aleatório por execução).
- ``SCREENSHARE_LINK_HOURS``: validade do link da sala, renovável pelo líder (padrão 6).
- ``SCREENSHARE_IDLE_MINUTES``: sem ninguém transmitindo por esse tempo, o link é removido (padrão 10).
- ``SCREENSHARE_MAX_VIEWERS``: máximo de espectadores simultâneos (padrão 8).
- ``SCREENSHARE_TURN_URL`` / ``_USER`` / ``_PASS``: servidor TURN opcional para redes restritivas.
"""
import logging
import os
import secrets
from typing import Optional

import discord
from discord.ext import commands

from services.screenshare import ScreenShareServer

log = logging.getLogger("fenrir.screenshare")


class ScreenShare(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.server: Optional[ScreenShareServer] = None
        # Por sala (id do canal de voz): se membros além do dono podem compartilhar.
        self._allow_members: dict[int, bool] = {}
        self._owners: dict[int, int] = {}  # canal de voz -> id do dono

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
            get_participants=self._participants,
            can_share=self._can_share_uid,
            is_leader=self._is_leader_uid,
            on_first_share=self._on_first_share,
            link_ttl=float(os.getenv("SCREENSHARE_LINK_HOURS", "6")) * 3600,
            idle_seconds=float(os.getenv("SCREENSHARE_IDLE_MINUTES", "10")) * 60,
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

    async def set_allow_members(self, channel_id: int, value: bool) -> None:
        self._allow_members[channel_id] = value
        if self.server is not None:
            await self.server.refresh(channel_id)  # painéis abertos atualizam o botão Compartilhar

    def set_owner(self, channel_id: int, user_id: int) -> None:
        self._owners[channel_id] = user_id

    def can_share(self, user_id: int, channel_id: int) -> bool:
        return self._owners.get(channel_id) == user_id or self.allow_members(channel_id)

    def link(self, channel_id: int, user_id: int) -> str:
        assert self.server is not None
        return self.server.link(channel_id, user_id)

    # -- callbacks do servidor web

    def _can_share_uid(self, room_id: int, uid: str) -> bool:
        return self.can_share(int(uid), room_id)

    def _is_leader_uid(self, room_id: int, uid: str) -> bool:
        return self._owners.get(room_id) == int(uid)

    def _participants(self, room_id: int) -> list[dict]:
        """Membros na call, com nome e foto (ids como string: passam de 2^53)."""
        channel = self.bot.get_channel(room_id)
        if not isinstance(channel, discord.VoiceChannel):
            return []
        return [
            {"id": str(m.id), "name": m.display_name, "avatar": m.display_avatar.with_size(64).url}
            for m in channel.members if not m.bot
        ]

    # -- eventos

    async def _on_first_share(self, room_id: int, user_id: int) -> None:
        """Única mensagem no canal: quando a sala passa a ter alguém compartilhando.

        O resto (quem assiste quem, quem entrou ou saiu, renovações) fica na janela
        de atividade do próprio painel.
        """
        channel = self.bot.get_channel(room_id)
        if channel is None:
            return
        try:
            await channel.send(
                f"🖥️ <@{user_id}> começou a compartilhar a tela. Abra o **Painel de telas** para assistir.",
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Quem sai da call perde a transmissão; quem entra ou sai atualiza a lista dos painéis."""
        if self.server is None or before.channel == after.channel:
            return
        if before.channel is not None:
            await self.server.drop_user(before.channel.id, member.id)
            await self.server.refresh(before.channel.id)
        if after.channel is not None:
            await self.server.refresh(after.channel.id)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        self._allow_members.pop(channel.id, None)
        self._owners.pop(channel.id, None)
        if self.server is not None:
            await self.server.revoke(channel.id, "a sala foi excluída")


async def setup(bot):
    await bot.add_cog(ScreenShare(bot))
