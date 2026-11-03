"""Servidor HTTP local do painel de cogs (aiohttp), preso a 127.0.0.1.

Como o painel controla o bot, ele se protege de páginas maliciosas abertas no mesmo navegador:
  * só aceita o header ``Host`` de localhost com a porta certa (contra DNS rebinding);
  * toda rota ``/api`` exige o token gerado a cada execução, entregue apenas na página
    inicial (outra origem não consegue ler a página, então não obtém o token).
"""
from __future__ import annotations

import hmac
import logging
import secrets
from pathlib import Path

from aiohttp import web

from devpanel.registry import ExtensionRegistry

log = logging.getLogger("fenrir.devpanel")

STATIC_DIR = Path(__file__).resolve().parent / "static"
TOKEN_HEADER = "X-Panel-Token"


class PanelServer:
    def __init__(self, registry: ExtensionRegistry, host: str = "127.0.0.1", port: int = 8765):
        self.registry = registry
        self.host = host
        self.port = port
        self.token = secrets.token_urlsafe(24)
        self.allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
        self._runner: web.AppRunner | None = None
        self.app = self._build_app()

    # ── app ──────────────────────────────────────────────────────────────────

    def _build_app(self) -> web.Application:
        app = web.Application(middlewares=[self._guard])
        app.router.add_get("/", self._index)
        app.router.add_get("/api/cogs", self._list)
        app.router.add_post("/api/cogs/toggle", self._toggle)
        app.router.add_post("/api/cogs/bulk", self._bulk)
        app.router.add_post("/api/sync", self._sync)
        return app

    @web.middleware
    async def _guard(self, request: web.Request, handler):
        if request.headers.get("Host", "") not in self.allowed_hosts:
            return web.json_response({"error": "host não permitido"}, status=403)
        if request.path.startswith("/api/"):
            given = request.headers.get(TOKEN_HEADER, "")
            if not hmac.compare_digest(given.encode(), self.token.encode()):
                return web.json_response({"error": "token inválido"}, status=403)
        return await handler(request)

    @staticmethod
    async def _json(request: web.Request) -> dict:
        try:
            data = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text='{"error": "JSON inválido"}', content_type="application/json")
        if not isinstance(data, dict):
            raise web.HTTPBadRequest(text='{"error": "corpo deve ser um objeto"}', content_type="application/json")
        return data

    # ── rotas ────────────────────────────────────────────────────────────────

    async def _index(self, request: web.Request) -> web.Response:
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8").replace("__PANEL_TOKEN__", self.token)
        return web.Response(text=html, content_type="text/html",
                            headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY"})

    async def _list(self, request: web.Request) -> web.Response:
        return web.json_response(self.registry.snapshot())

    async def _toggle(self, request: web.Request) -> web.Response:
        data = await self._json(request)
        module, enabled = data.get("module"), data.get("enabled")
        if not isinstance(module, str) or not isinstance(enabled, bool):
            return web.json_response({"error": "informe module (texto) e enabled (booleano)"}, status=400)
        try:
            item = await self.registry.set_enabled(module, enabled)
        except KeyError:
            return web.json_response({"error": f"módulo desconhecido: {module}"}, status=404)
        return web.json_response({"cog": item, "sync": self.registry.snapshot()["sync"]})

    async def _bulk(self, request: web.Request) -> web.Response:
        data = await self._json(request)
        enabled, modules = data.get("enabled"), data.get("modules")
        if not isinstance(enabled, bool) or not (modules is None or (
                isinstance(modules, list) and all(isinstance(m, str) for m in modules))):
            return web.json_response({"error": "informe enabled (booleano) e modules (lista, opcional)"}, status=400)
        try:
            result = await self.registry.set_many(enabled, modules)
        except KeyError as exc:
            return web.json_response({"error": f"módulo desconhecido: {exc.args[0]}"}, status=404)
        result["sync"] = self.registry.snapshot()["sync"]
        return web.json_response(result)

    async def _sync(self, request: web.Request) -> web.Response:
        result = await self.registry.sync_now()
        return web.json_response(result, status=200 if result["ok"] else 502)

    # ── ciclo de vida ────────────────────────────────────────────────────────

    async def start(self) -> None:
        self._runner = web.AppRunner(self.app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        log.info("Painel de cogs em http://localhost:%d (somente esta máquina)", self.port)

    async def stop(self) -> None:
        await self.registry.shutdown()
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
