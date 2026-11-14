import pytest
from unittest.mock import AsyncMock, Mock
import discord
from aiohttp.test_utils import TestClient, TestServer

from cogs.moderacao.cria_canal import VoiceControlView
from cogs.moderacao.tela import ScreenShare
from services.screenshare import (
    ROLE_HOST, ROLE_VIEWER, ScreenShareServer, make_token, verify_token,
)

SECRET = "segredo-de-teste"


def test_token_valido_e_adulterado():
    t = make_token(SECRET, 10, 20, ROLE_HOST, now=1000)
    c = verify_token(SECRET, t, now=1001)
    assert (c.room_id, c.user_id, c.role) == (10, 20, ROLE_HOST)
    assert verify_token("outro", t, now=1001) is None
    assert verify_token(SECRET, t.replace(".host.", ".viewer."), now=1001) is None
    assert verify_token(SECRET, "lixo", now=1001) is None


def test_token_expirado():
    t = make_token(SECRET, 1, 2, ROLE_VIEWER, ttl=10, now=1000)
    assert verify_token(SECRET, t, now=1011) is None


@pytest.fixture
async def client():
    events = []

    async def cb(room, user, live):
        events.append((room, user, live))

    server = ScreenShareServer(SECRET, "http://x", max_viewers=1, on_host_change=cb)
    c = TestClient(TestServer(server.app))
    await c.start_server()
    c.srv, c.events = server, events
    yield c
    await c.close()


def _url(room, user, role):
    return f"/screen/ws?t={make_token(SECRET, room, user, role)}"


async def test_pagina_exige_token(client):
    assert (await client.get("/screen/5")).status == 403
    t = make_token(SECRET, 5, 1, ROLE_VIEWER)
    assert (await client.get(f"/screen/5?t={t}")).status == 200
    assert (await client.get(f"/screen/6?t={t}")).status == 403


async def test_fluxo_sinalizacao(client):
    host = await client.ws_connect(_url(5, 1, ROLE_HOST))
    assert (await host.receive_json())["role"] == ROLE_HOST
    viewer = await client.ws_connect(_url(5, 2, ROLE_VIEWER))
    assert (await viewer.receive_json())["live"] is False

    await host.send_json({"type": "live"})
    assert (await viewer.receive_json())["type"] == "host-live"
    joined = await host.receive_json()
    assert joined["type"] == "viewer-joined"

    await host.send_json({"type": "offer", "to": joined["id"], "data": {"sdp": "o"}})
    assert (await viewer.receive_json()) == {"type": "offer", "data": {"sdp": "o"}}
    await viewer.send_json({"type": "answer", "data": {"sdp": "a"}})
    got = await host.receive_json()
    assert got["type"] == "answer" and got["from"] == joined["id"]

    assert client.events == [(5, 1, True)]
    assert client.srv.is_live(5) and client.srv.host_user(5) == 1

    assert await client.srv.stop_room(5)
    assert (await viewer.receive_json())["type"] == "host-left"
    await host.close()
    await viewer.close()


async def test_segundo_host_e_limite_de_espectadores(client):
    host = await client.ws_connect(_url(7, 1, ROLE_HOST))
    await host.receive_json()
    outro = await client.ws_connect(_url(7, 3, ROLE_HOST))
    assert (await outro.receive_json())["type"] == "error"

    v1 = await client.ws_connect(_url(7, 4, ROLE_VIEWER))
    await v1.receive_json()
    v2 = await client.ws_connect(_url(7, 5, ROLE_VIEWER))
    assert (await v2.receive_json())["type"] == "error"
    for w in (host, v1):
        await w.close()


async def test_token_invalido_no_ws(client):
    resp = await client.get("/screen/ws?t=ruim")
    assert resp.status == 403


# ── Painel ───────────────────────────────────────────────────────────────────

def _interaction(user, voice_channel):
    i = Mock()
    i.user = user
    user.voice = Mock(channel=voice_channel)
    i.response.send_message = AsyncMock()
    i.response.edit_message = AsyncMock()
    return i


@pytest.fixture
def painel():
    bot = Mock()
    cog = ScreenShare(bot)
    cog.server = Mock()
    cog.server.link = Mock(return_value="http://x/screen/1?t=abc")
    cog.server.host_user = Mock(return_value=None)
    cog.server.stop_room = AsyncMock()
    bot.get_cog = Mock(return_value=cog)
    canal = Mock(spec=discord.VoiceChannel, id=99)
    dono, membro = Mock(spec=discord.Member, id=1), Mock(spec=discord.Member, id=2)
    view = VoiceControlView(bot, dono, canal)
    return view, cog, canal, dono, membro


async def test_membro_bloqueado_ate_dono_liberar(painel):
    view, cog, canal, dono, membro = painel
    i = _interaction(membro, canal)
    await view.share_button.callback(i)
    assert "não liberou" in i.response.send_message.call_args.args[0]

    # só o dono mexe no botão de permissão
    i = _interaction(membro, canal)
    await view.allow_share_button.callback(i)
    assert "Apenas o dono" in i.response.send_message.call_args.args[0]

    i = _interaction(dono, canal)
    await view.allow_share_button.callback(i)
    assert cog.allow_members(99) and "liberado" in view.allow_share_button.label

    i = _interaction(membro, canal)
    await view.share_button.callback(i)
    assert "Abrir sala" in i.response.send_message.call_args.args[0]


async def test_dono_compartilha_e_fora_da_call_nao(painel):
    view, cog, canal, dono, membro = painel
    i = _interaction(dono, canal)
    await view.share_button.callback(i)
    cog.server.link.assert_called_with(99, 1, ROLE_HOST)

    i = _interaction(dono, Mock())  # em outra call
    await view.share_button.callback(i)
    assert "Entre nesta call" in i.response.send_message.call_args.args[0]


async def test_parar_so_dono_ou_quem_compartilha(painel):
    view, cog, canal, dono, membro = painel
    cog.server.host_user.return_value = 2
    outro = Mock(spec=discord.Member, id=3)
    i = _interaction(outro, canal)
    await view.stop_share_button.callback(i)
    cog.server.stop_room.assert_not_called()
    await view.stop_share_button.callback(_interaction(membro, canal))
    cog.server.stop_room.assert_awaited_once_with(99)


def test_filter_enabled():
    from services.extensions import filter_enabled
    mods = ["cogs.moderacao.tela", "cogs.copa.selfbot_trap", "cogs.economia.loja"]
    assert filter_enabled(mods, "") == mods
    assert filter_enabled(mods, None) == mods
    assert filter_enabled(mods, "tela, selfbot_trap") == mods[:2]
    assert filter_enabled(mods, "cogs.economia.loja") == [mods[2]]
