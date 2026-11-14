"""Descoberta das extensões (cogs) do bot a partir da pasta ``cogs/``.

Mesma regra usada no boot: pacotes com ``setup()`` no ``__init__.py`` (ex: ``cogs.antispam``)
são uma única extensão e não são percorridos; nas demais pastas, cada ``.py`` é uma extensão.
"""
from __future__ import annotations

import os


def module_defines_setup(path: str) -> bool:
    """Heurística leve: detecta se um arquivo exporta `setup`, sem importá-lo."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return "def setup(" in f.read()
    except OSError:
        return False


def discover_extensions(base_dir: str) -> list[str]:
    """Nomes de módulo (``cogs.economia.loja``) das extensões, na ordem da varredura."""
    modules: list[str] = []
    cogs_dir = os.path.join(base_dir, "cogs")
    for root, dirs, files in os.walk(cogs_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        init_path = os.path.join(root, "__init__.py")
        if os.path.exists(init_path) and module_defines_setup(init_path):
            rel = os.path.relpath(root, base_dir)
            modules.append(rel.replace(os.sep, "."))
            dirs[:] = []  # submódulos já vêm pelo pacote
            continue

        for filename in files:
            if filename.endswith(".py") and filename != "__init__.py":
                rel = os.path.relpath(os.path.join(root, filename), base_dir)
                modules.append(rel.replace(os.sep, ".")[:-3])
    return modules


def filter_enabled(modules: list[str], enabled: str | None) -> list[str]:
    """Restringe as extensões às listadas em ``enabled`` (ex: ``ENABLED_COGS``).

    ``enabled`` é uma lista separada por vírgula; cada item casa com o nome completo
    do módulo (``cogs.moderacao.tela``) ou só com o último trecho (``tela``).
    Vazio/None mantém todas.
    """
    wanted = {item.strip() for item in (enabled or "").split(",") if item.strip()}
    if not wanted:
        return modules
    return [m for m in modules if m in wanted or m.rsplit(".", 1)[-1] in wanted]
