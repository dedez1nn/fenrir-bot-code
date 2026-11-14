import asyncio

import pytest
from unittest.mock import AsyncMock, Mock
import discord
from aiohttp.test_utils import TestClient, TestServer

from cogs.moderacao.cria_canal import VoiceControlView
from cogs.moderacao.tela import ScreenShare
from services.extensions import filter_enabled
from services.screenshare import ScreenShareServer, make_token, verify_token

SECRET = "segredo-de-teste"
ROOM = 5
PEOPLE = [{"id": str(i), "name": f"user{i}", "avatar": None} for i in (1, 2, 3)]


def test_token_valido_e_adulterado():
    t = make_token(SECRET, 10, 20, now=1000)
    c = verify_token(SECRET, t, now=1001)
    assert (c.room_id, c.user_id) == (10, 20)
    assert verify_token("outro", t, now=1001) is None
    assert verify_token(SECRET, t.replace(".member.", ".admin."), now=1001) is None
    assert verify_token(SECRET, "lixo", now=1001) is None


def test_token_expirado():
    assert verify_token(SECRET, make_token(SECRET, 1, 2, ttl=10, now=1000), now=1011) is None


@pytest.fixture
async def client():
    events, allowed = [], {"1"}

    async def cb(room, user, live):
        events.append((room, user, live))

    server = ScreenShareServer(
        SECRET, "http://x", max_viewers=1,
        get_participants=lambda room: PEOPLE if room == ROOM else [],
        can_share=lambda room, uid: uid in allowed,
        on_host_change=cb,
    )
    c = TestClient(TestServer(server.app))
    await c.start_server()
    c.srv, c.events, c.allowed = server, events, allowed
    yield c
    await c.close()


def _url(uid, room=ROOM):
    return f"/screen/ws?t={make_token(SECRET, room, uid)}"


async def _connect(client, uid):
    ws = await client.ws_connect(_url(uid))
    assert (await ws.receive_json())["type"] == "welcome"
    return ws


async def _until(ws, kind, timeout=3):
    async def loop():
        while True:
            msg = await ws.receive_json()
            if msg["type"] == kind:
                return msg
    try:
        return await asyncio.wait_for(loop(), timeout)
    except asyncio.TimeoutError:
        pytest.fail(f"mensagem {kind!r} não chegou")


async def test_pagina_exige_token(client):
    assert (await client.get(f"/screen/{ROOM}")).status == 403
    t = make_token(SECRET, ROOM, 1)
    resp = await client.get(f"/screen/{ROOM}?t={t}")
    assert resp.status == 200 and "Painel de telas" in await resp.text()
    assert (await client.get(f"/screen/6?t={t}")).status == 403


async def test_fora_da_call_nao_entra(client):
    ws = await client.ws_connect(_url(99))
    assert (await ws.receive_json())["type"] == "error"
    assert (await client.get("/screen/ws?t=ruim")).status == 403


async def test_estado_e_permissao_de_compartilhar(client):
    dono = await _connect(client, 1)
    st = await _until(dono, "state")
    assert st["can_share"] is True and [p["id"] for p in st["people"]] == ["1", "2", "3"]

    membro = await _connect(client, 2)
    assert (await _until(membro, "state"))["can_share"] is False
    await membro.send_json({"type": "live"})
    assert (await _until(membro, "denied"))["type"] == "denied"
    assert client.events == []
    for w in (dono, membro):
        await w.close()


async def test_fluxo_de_sinalizacao_varios_hosts_e_viewers(client):
    client.allowed.update({"2"})
    host1, host2, viewer = await _connect(client, 1), await _connect(client, 2), await _connect(client, 3)

    await host1.send_json({"type": "live"})
    await host2.send_json({"type": "live"})
    st = await _until(viewer, "state")
    while not all(p["live"] for p in st["people"][:2]):
        st = await _until(viewer, "state")
    assert client.srv.live_users(ROOM) == ["1", "2"]

    await viewer.send_json({"type": "watch", "target": "1"})
    st = await _until(viewer, "state")
    while next(p for p in st["people"] if p["id"] == "1")["viewers"] != ["3"]:
        st = await _until(viewer, "state")
    cid = (await _until(host1, "viewer-joined"))["id"]

    await host1.send_json({"type": "offer", "to": cid, "data": {"sdp": "o"}})
    got = await _until(viewer, "offer")
    assert got["from"] == "1" and got["data"] == {"sdp": "o"}
    await viewer.send_json({"type": "answer", "to": "1", "data": {"sdp": "a"}})
    ans = await _until(host1, "answer")
    assert ans["from"] == cid

    # quem não assiste o host 2 não consegue mandar sinalização para ele
    await viewer.send_json({"type": "candidate", "to": "2", "data": {}})

    # parar a transmissão avisa os espectadores e o callback
    await host1.send_json({"type": "stop"})
    assert (await _until(viewer, "host-left"))["from"] == "1"
    await asyncio.sleep(0.05)
    assert (ROOM, 1, False) in client.events
    for w in (host1, host2, viewer):
        await w.close()


async def test_limite_de_espectadores_por_tela(client):
    host = await _connect(client, 1)
    await host.send_json({"type": "live"})
    v1, v2 = await _connect(client, 2), await _connect(client, 3)
    await v1.send_json({"type": "watch", "target": "1"})
    await _until(host, "viewer-joined")
    await v2.send_json({"type": "watch", "target": "1"})
    assert "máximo" in (await _until(v2, "error"))["message"]
    for w in (host, v1, v2):
        await w.close()


async def test_drop_user_encerra_transmissao(client):
    host, viewer = await _connect(client, 1), await _connect(client, 2)
    await host.send_json({"type": "live"})
    await viewer.send_json({"type": "watch", "target": "1"})
    await _until(host, "viewer-joined")
    await client.srv.drop_user(ROOM, 1)
    assert (await _until(viewer, "host-left"))["from"] == "1"
    assert client.srv.live_users(ROOM) == []
    await viewer.close()


# ── Cog e painel ─────────────────────────────────────────────────────────────

def test_participantes_com_nome_e_foto():
    bot = Mock()
    canal = Mock(spec=discord.VoiceChannel)
    humano, robo = Mock(id=10, bot=False, display_name="Ana"), Mock(id=11, bot=True, display_name="Bot")
    humano.display_avatar.with_size.return_value.url = "https://cdn.discordapp.com/a.png?size=64"
    canal.members = [humano, robo]
    bot.get_channel.return_value = canal
    cog = ScreenShare(bot)
    assert cog._participants(5) == [{"id": "10", "name": "Ana", "avatar": "https://cdn.discordapp.com/a.png?size=64"}]
    bot.get_channel.return_value = None
    assert cog._participants(5) == []


def test_permissao_dono_e_liberacao():
    cog = ScreenShare(Mock())
    cog.set_owner(99, 1)
    assert cog.can_share(1, 99) and not cog.can_share(2, 99)
    cog._allow_members[99] = True
    assert cog.can_share(2, 99)


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
    cog.server.refresh = AsyncMock()
    cog.server.stop_room = AsyncMock(return_value=2)
    cog.server.stop_user = AsyncMock(return_value=True)
    bot.get_cog = Mock(return_value=cog)
    canal = Mock(spec=discord.VoiceChannel, id=99)
    dono, membro = Mock(spec=discord.Member, id=1), Mock(spec=discord.Member, id=2)
    return VoiceControlView(bot, dono, canal), cog, canal, dono, membro


async def test_painel_entrega_link_pessoal_a_quem_esta_na_call(painel):
    view, cog, canal, dono, membro = painel
    await view.share_button.callback(_interaction(membro, canal))
    cog.server.link.assert_called_with(99, 2)

    i = _interaction(membro, Mock())  # em outra call
    await view.share_button.callback(i)
    assert "Entre nesta call" in i.response.send_message.call_args.args[0]


async def test_so_dono_libera_membros(painel):
    view, cog, canal, dono, membro = painel
    i = _interaction(membro, canal)
    await view.allow_share_button.callback(i)
    assert "Apenas o dono" in i.response.send_message.call_args.args[0]

    await view.allow_share_button.callback(_interaction(dono, canal))
    assert cog.allow_members(99) and "liberado" in view.allow_share_button.label
    cog.server.refresh.assert_awaited_with(99)


async def test_parar_dono_para_todas_membro_so_a_propria(painel):
    view, cog, canal, dono, membro = painel
    await view.stop_share_button.callback(_interaction(dono, canal))
    cog.server.stop_room.assert_awaited_once_with(99)
    await view.stop_share_button.callback(_interaction(membro, canal))
    cog.server.stop_user.assert_awaited_once_with(99, 2)


def test_filter_enabled():
    mods = ["cogs.moderacao.tela", "cogs.copa.selfbot_trap", "cogs.economia.loja"]
    assert filter_enabled(mods, "") == mods
    assert filter_enabled(mods, None) == mods
    assert filter_enabled(mods, "tela, selfbot_trap") == mods[:2]
    assert filter_enabled(mods, "cogs.economia.loja") == [mods[2]]
