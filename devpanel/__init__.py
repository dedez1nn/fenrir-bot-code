"""Painel local para ligar e desligar os cogs do bot (somente desenvolvimento).

Ative com ``DEV_PANEL=1`` no ``.env``. Variáveis opcionais:
  DEV_PANEL_PORT      porta (padrão 8765)
  DEV_PANEL_AUTOSYNC  1/0: sincroniza os slash commands sozinho após mudar (padrão 1)
"""
from __future__ import annotations

import logging
import os

from devpanel.registry import ExtensionRegistry
from devpanel.server import PanelServer

log = logging.getLogger("fenrir.devpanel")


async def start_dev_panel(bot, base_dir: str) -> PanelServer | None:
    """Sobe o painel preso a 127.0.0.1. Retorna None se a porta estiver ocupada."""
    try:
        port = int(os.getenv("DEV_PANEL_PORT", "8765"))
    except ValueError:
        log.warning("DEV_PANEL_PORT inválida; usando 8765")
        port = 8765
    autosync = os.getenv("DEV_PANEL_AUTOSYNC", "1") != "0"
    server = PanelServer(ExtensionRegistry(bot, base_dir, autosync=autosync), port=port)
    try:
        await server.start()
    except OSError as exc:
        log.warning("Painel não iniciou (porta %d): %s", port, exc)
        return None
    return server


__all__ = ["ExtensionRegistry", "PanelServer", "start_dev_panel"]
