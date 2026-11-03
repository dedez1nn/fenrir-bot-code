"""Registro das extensões (cogs) do bot: estado, liga/desliga e sincronização de comandos.

É a camada sem HTTP do painel local, para ser testável. Liga e desliga usam
``load_extension``/``unload_extension`` do discord.py, então o efeito é imediato
(listeners e comandos somem na hora). Os slash commands só mudam no Discord depois de
``tree.sync()``, que é agendado com atraso (debounce) para não estourar o rate limit.
"""
from __future__ import annotations

import asyncio
import logging
import math
import sys
import time
from typing import Any

from services.extensions import discover_extensions

log = logging.getLogger("fenrir.devpanel")

GROUP_LABELS = {
    "economia": "Economia", "moderacao": "Moderação", "progressao": "Progressão",
    "interface": "Interface", "apis": "APIs externas", "antinuke": "Segurança",
    "antispam": "Segurança", "copa": "Copa", "geral": "Geral",
}
ACRONYMS = {"xp": "XP", "api": "API", "pix": "PIX", "gnews": "GNews", "lol": "LoL", "cria": "Cria"}


def _group_of(module: str) -> str:
    parts = module.split(".")           # cogs.<grupo>.<nome>  ou  cogs.<nome>
    return parts[1] if len(parts) > 2 else "geral"


def _label_of(module: str) -> str:
    last = module.split(".")[-1]
    words = last.replace("-", "_").split("_")
    return " ".join(ACRONYMS.get(w.lower(), w.capitalize()) for w in words if w)


def _short_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:300]


class ExtensionRegistry:
    def __init__(self, bot, base_dir: str, autosync: bool = True, sync_delay: float = 3.0):
        self.bot = bot
        self.base_dir = base_dir
        self.autosync = autosync
        self.sync_delay = sync_delay
        self.started_at = time.time()
        self.pending_sync = False
        self.sync_error: str | None = None
        self.last_sync_at: float | None = None
        self._lock = asyncio.Lock()
        self._sync_lock = asyncio.Lock()
        self._sync_task: asyncio.Task | None = None
        self._errors: dict[str, str] = {}
        self._info: dict[str, dict[str, Any]] = {}   # último estado conhecido (vale p/ módulos desligados)

    # ── descoberta e captura de informações ──────────────────────────────────

    def modules(self) -> list[str]:
        return sorted(discover_extensions(self.base_dir))

    def _capture(self, module: str) -> None:
        """Guarda cogs, comandos e descrição do módulo enquanto ele está carregado."""
        if module not in self.bot.extensions:
            return
        cogs = [c for c in self.bot.cogs.values()
                if c.__module__ == module or c.__module__.startswith(module + ".")]
        commands: list[str] = []
        for c in cogs:
            commands += [f"/{cmd.qualified_name}" for cmd in c.get_app_commands()]
            commands += [f"!{cmd.qualified_name}" for cmd in c.get_commands()]
        desc = ""
        for c in cogs:
            doc = (type(c).__doc__ or "").strip()
            if doc:
                desc = doc.splitlines()[0].strip()
                break
        if not desc:
            doc = (getattr(sys.modules.get(module), "__doc__", None) or "").strip()
            desc = doc.splitlines()[0].strip() if doc else ""
        self._info[module] = {"cogs": [type(c).__name__ for c in cogs], "commands": commands, "description": desc}

    def _item(self, module: str) -> dict[str, Any]:
        self._capture(module)
        info = self._info.get(module, {})
        return {
            "module": module,
            "group": _group_of(module),
            "group_label": GROUP_LABELS.get(_group_of(module), _group_of(module).title()),
            "label": _label_of(module),
            "description": info.get("description", ""),
            "cogs": info.get("cogs", []),
            "commands": info.get("commands", []),
            "loaded": module in self.bot.extensions,
            "error": self._errors.get(module),
        }

    # ── estado ───────────────────────────────────────────────────────────────

    def _bot_info(self) -> dict[str, Any]:
        latency = getattr(self.bot, "latency", float("nan"))
        user = getattr(self.bot, "user", None)
        return {
            "name": str(user) if user else None,
            "ready": user is not None,
            "latency_ms": None if latency is None or not math.isfinite(latency) else round(latency * 1000),
            "guilds": len(getattr(self.bot, "guilds", []) or []),
            "uptime_s": round(time.time() - self.started_at),
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "bot": self._bot_info(),
            "sync": {"auto": self.autosync, "pending": self.pending_sync,
                     "error": self.sync_error, "last_at": self.last_sync_at},
            "cogs": [self._item(m) for m in self.modules()],
        }

    # ── ações ────────────────────────────────────────────────────────────────

    async def _apply(self, module: str, enabled: bool) -> bool:
        """Liga/desliga uma extensão. Retorna True se o estado mudou. Erros ficam em `_errors`."""
        loaded = module in self.bot.extensions
        if enabled == loaded:
            return False
        try:
            if enabled:
                await self.bot.load_extension(module)
            else:
                self._capture(module)           # guarda comandos antes de sumirem
                await self.bot.unload_extension(module)
        except Exception as exc:
            self._errors[module] = _short_error(exc)
            log.warning("Painel: falha ao %s '%s': %s", "ligar" if enabled else "desligar", module, exc)
            return False
        self._errors.pop(module, None)
        log.info("Painel: '%s' %s", module, "ligado" if enabled else "desligado")
        return True

    async def set_enabled(self, module: str, enabled: bool) -> dict[str, Any]:
        if module not in self.modules():
            raise KeyError(module)
        async with self._lock:
            changed = await self._apply(module, enabled)
        if changed:
            self._schedule_sync()
        return self._item(module)

    async def set_many(self, enabled: bool, modules: list[str] | None = None) -> dict[str, Any]:
        known = self.modules()
        targets = known if modules is None else modules
        unknown = [m for m in targets if m not in known]
        if unknown:
            raise KeyError(unknown[0])
        changed_any = False
        async with self._lock:
            for m in targets:
                changed_any |= await self._apply(m, enabled)
        if changed_any:
            self._schedule_sync()
        items = [self._item(m) for m in targets]
        return {"cogs": items, "errors": sum(1 for i in items if i["error"])}

    # ── sincronização dos slash commands ─────────────────────────────────────

    def _schedule_sync(self) -> None:
        """Agenda um tree.sync com atraso; várias mudanças seguidas viram um sync só."""
        self.pending_sync = True
        if not self.autosync:
            return
        task = self._sync_task
        if task and not task.done() and not self._sync_lock.locked():
            task.cancel()                       # ainda esperando: reinicia o atraso
        # se um sync já está em andamento, ele termina e este novo task faz outro depois
        self._sync_task = asyncio.create_task(self._debounced_sync())

    async def _debounced_sync(self) -> None:
        await asyncio.sleep(self.sync_delay)
        await self.sync_now()

    async def sync_now(self) -> dict[str, Any]:
        async with self._sync_lock:
            try:
                synced = await self.bot.tree.sync()
            except Exception as exc:
                self.sync_error = _short_error(exc)
                log.warning("Painel: tree.sync falhou: %s", exc)
                return {"ok": False, "error": self.sync_error}
            self.pending_sync = False
            self.sync_error = None
            self.last_sync_at = time.time()
            return {"ok": True, "commands": len(synced)}

    async def shutdown(self) -> None:
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
