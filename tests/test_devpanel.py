import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from devpanel.registry import ExtensionRegistry, _label_of
from devpanel.server import PanelServer
from services.extensions import discover_extensions


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def base_dir(tmp_path):
    cogs = tmp_path / "cogs"
    (cogs / "grupo").mkdir(parents=True)
    (cogs / "pkg").mkdir()
    (cogs / "__pycache__").mkdir()
    (cogs / "__init__.py").write_text("")
    (cogs / "solto.py").write_text("async def setup(bot): ...\n")
    (cogs / "grupo" / "__init__.py").write_text("")            # sem setup: cada .py é um cog
    (cogs / "grupo" / "xp_cog.py").write_text("async def setup(bot): ...\n")
    (cogs / "pkg" / "__init__.py").write_text("async def setup(bot): ...\n")   # pacote-cog
    (cogs / "pkg" / "sub.py").write_text("x = 1\n")
    (cogs / "__pycache__" / "lixo.py").write_text("")
    return str(tmp_path)


class FakeBot:
    def __init__(self):
        self.extensions: dict = {}
        self.cogs: dict = {}
        self.fail: dict[str, Exception] = {}
        self.tree = SimpleNamespace(sync=AsyncMock(return_value=[1, 2]))
        self.user = None
        self.latency = float("nan")
        self.guilds: list = []

    async def load_extension(self, name):
        if name in self.fail:
            raise self.fail[name]
        cmd = SimpleNamespace(qualified_name=name.split(".")[-1])
        cls = type("Cog", (), {
            "__module__": name, "__doc__": f"Descrição de {name}.\nSegunda linha.",
            "get_app_commands": lambda self: [cmd], "get_commands": lambda self: [],
        })
        self.extensions[name] = object()
        self.cogs[name] = cls()

    async def unload_extension(self, name):
        self.extensions.pop(name)
        self.cogs.pop(name)


@pytest.fixture
def bot():
    return FakeBot()


@pytest.fixture
def registry(bot, base_dir):
    return ExtensionRegistry(bot, base_dir, autosync=True, sync_delay=0.05)


# ─── Descoberta ──────────────────────────────────────────────────────────────

def test_discover_extensions(base_dir):
    mods = set(discover_extensions(base_dir))
    assert mods == {"cogs.solto", "cogs.grupo.xp_cog", "cogs.pkg"}     # pacote conta como um; sem __pycache__
    assert "cogs.pkg.sub" not in mods and "cogs.grupo" not in mods


def test_discover_extensions_do_projeto_real():
    import os
    mods = discover_extensions(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert "cogs.antispam" in mods and "cogs.antispam.cog" not in mods
    assert "cogs.apis.riot" in mods
    assert all(not m.endswith("__init__") for m in mods)


def test_label():
    assert _label_of("cogs.progressao.xp") == "XP"
    assert _label_of("cogs.economia.fenrir_coins") == "Fenrir Coins"
    assert _label_of("cogs.apis.lol_matchup") == "LoL Matchup"


# ─── Registro ────────────────────────────────────────────────────────────────

async def test_snapshot_inicial(registry, bot):
    for m in ("cogs.solto", "cogs.grupo.xp_cog"):
        await bot.load_extension(m)
    snap = registry.snapshot()
    by = {c["module"]: c for c in snap["cogs"]}
    assert set(by) == {"cogs.solto", "cogs.grupo.xp_cog", "cogs.pkg"}
    assert by["cogs.solto"]["loaded"] and by["cogs.solto"]["group"] == "geral"
    assert by["cogs.grupo.xp_cog"]["group"] == "grupo" and by["cogs.grupo.xp_cog"]["label"] == "XP Cog"
    assert not by["cogs.pkg"]["loaded"]
    assert by["cogs.solto"]["description"] == "Descrição de cogs.solto."
    assert by["cogs.solto"]["commands"] == ["/solto"]
    assert snap["bot"]["ready"] is False and snap["bot"]["latency_ms"] is None


async def test_desligar_e_ligar_mantem_informacoes(registry, bot):
    await bot.load_extension("cogs.solto")
    item = await registry.set_enabled("cogs.solto", False)
    assert item["loaded"] is False and "cogs.solto" not in bot.extensions
    assert item["commands"] == ["/solto"]                      # lembra dos comandos mesmo desligado
    item = await registry.set_enabled("cogs.solto", True)
    assert item["loaded"] is True and "cogs.solto" in bot.extensions


async def test_modulo_desconhecido(registry):
    with pytest.raises(KeyError):
        await registry.set_enabled("os", False)
    with pytest.raises(KeyError):
        await registry.set_many(True, ["cogs.solto", "nao.existe"])


async def test_falha_ao_ligar_registra_erro(registry, bot):
    bot.fail["cogs.pkg"] = RuntimeError("dependência faltando")
    item = await registry.set_enabled("cogs.pkg", True)
    assert item["loaded"] is False and "RuntimeError: dependência faltando" in item["error"]
    assert registry.pending_sync is False                      # nada mudou, nada a sincronizar
    del bot.fail["cogs.pkg"]
    item = await registry.set_enabled("cogs.pkg", True)        # sucesso limpa o erro
    assert item["loaded"] and item["error"] is None


async def test_set_many_todos(registry, bot):
    res = await registry.set_many(True)
    assert len(bot.extensions) == 3 and res["errors"] == 0
    res = await registry.set_many(False, ["cogs.solto"])
    assert set(bot.extensions) == {"cogs.grupo.xp_cog", "cogs.pkg"}
    res = await registry.set_many(False)
    assert bot.extensions == {} and len(res["cogs"]) == 3


async def test_sync_com_debounce(registry, bot):
    await registry.set_enabled("cogs.solto", True)
    await registry.set_enabled("cogs.pkg", True)
    await registry.set_enabled("cogs.solto", False)
    assert registry.pending_sync is True
    await asyncio.sleep(0.25)
    assert bot.tree.sync.await_count == 1                      # três mudanças viraram um sync
    assert registry.pending_sync is False and registry.last_sync_at is not None


async def test_sem_mudanca_nao_sincroniza(registry, bot):
    await registry.set_enabled("cogs.solto", False)            # já estava desligado
    await asyncio.sleep(0.15)
    assert bot.tree.sync.await_count == 0 and registry.pending_sync is False


async def test_autosync_desligado(bot, base_dir):
    reg = ExtensionRegistry(bot, base_dir, autosync=False, sync_delay=0.01)
    await reg.set_enabled("cogs.solto", True)
    await asyncio.sleep(0.1)
    assert bot.tree.sync.await_count == 0 and reg.pending_sync is True
    out = await reg.sync_now()
    assert out == {"ok": True, "commands": 2} and reg.pending_sync is False


async def test_falha_no_sync(registry, bot):
    bot.tree.sync.side_effect = RuntimeError("rate limit")
    await registry.set_enabled("cogs.solto", True)
    out = await registry.sync_now()
    assert out["ok"] is False and "rate limit" in registry.sync_error and registry.pending_sync is True
    bot.tree.sync.side_effect = None
    assert (await registry.sync_now())["ok"] and registry.sync_error is None


# ─── Servidor HTTP ───────────────────────────────────────────────────────────

@pytest.fixture
async def client(registry):
    panel = PanelServer(registry, port=0)
    server = TestServer(panel.app)
    await server.start_server()
    panel.allowed_hosts.add(f"{server.host}:{server.port}")
    cl = TestClient(server)
    await cl.start_server()
    cl.panel = panel
    yield cl
    await cl.close()


def H(client):
    return {"X-Panel-Token": client.panel.token}


async def test_pagina_entrega_token(client):
    r = await client.get("/")
    html = await r.text()
    assert r.status == 200 and client.panel.token in html and "__PANEL_TOKEN__" not in html
    assert r.headers["Cache-Control"] == "no-store"


async def test_api_exige_token_e_host(client):
    assert (await client.get("/api/cogs")).status == 403
    assert (await client.get("/api/cogs", headers={"X-Panel-Token": "errado"})).status == 403
    assert (await client.get("/api/cogs", headers={**H(client), "Host": "evil.com"})).status == 403
    assert (await client.get("/", headers={"Host": "evil.com"})).status == 403
    r = await client.get("/api/cogs", headers=H(client))
    assert r.status == 200 and len((await r.json())["cogs"]) == 3


async def test_api_toggle(client, bot):
    r = await client.post("/api/cogs/toggle", json={"module": "cogs.solto", "enabled": True}, headers=H(client))
    body = await r.json()
    assert r.status == 200 and body["cog"]["loaded"] is True and body["sync"]["pending"] is True
    assert "cogs.solto" in bot.extensions


@pytest.mark.parametrize("payload", [{}, {"module": "cogs.solto"}, {"module": 1, "enabled": True},
                                     {"module": "cogs.solto", "enabled": "sim"}])
async def test_api_toggle_valida_corpo(client, payload):
    r = await client.post("/api/cogs/toggle", json=payload, headers=H(client))
    assert r.status == 400


async def test_api_toggle_desconhecido_e_json_invalido(client):
    r = await client.post("/api/cogs/toggle", json={"module": "os", "enabled": False}, headers=H(client))
    assert r.status == 404
    r = await client.post("/api/cogs/toggle", data="nao e json", headers=H(client))
    assert r.status == 400
    r = await client.post("/api/cogs/toggle", json=[1, 2], headers=H(client))
    assert r.status == 400


async def test_api_bulk(client, bot):
    r = await client.post("/api/cogs/bulk", json={"enabled": True}, headers=H(client))
    body = await r.json()
    assert r.status == 200 and len(bot.extensions) == 3 and body["errors"] == 0
    r = await client.post("/api/cogs/bulk", json={"enabled": False, "modules": ["cogs.pkg"]}, headers=H(client))
    assert r.status == 200 and "cogs.pkg" not in bot.extensions
    assert (await client.post("/api/cogs/bulk", json={"enabled": 1}, headers=H(client))).status == 400
    assert (await client.post("/api/cogs/bulk", json={"enabled": True, "modules": "x"}, headers=H(client))).status == 400
    assert (await client.post("/api/cogs/bulk", json={"enabled": True, "modules": ["x.y"]}, headers=H(client))).status == 404


async def test_api_sync(client, bot):
    r = await client.post("/api/sync", json={}, headers=H(client))
    assert r.status == 200 and (await r.json()) == {"ok": True, "commands": 2}
    bot.tree.sync.side_effect = RuntimeError("falhou")
    assert (await client.post("/api/sync", json={}, headers=H(client))).status == 502
