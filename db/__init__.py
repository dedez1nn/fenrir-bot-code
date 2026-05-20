"""Camada de acesso a dados do Fenrir.

Este pacote provê:
- `pool`: gerenciamento do pool asyncpg compartilhado (`init_pool`, `close_pool`).
- `config`: carregamento e cache em memória de `server_config`.
- `migrate`: aplicação de migrações SQL e importação automática de JSONs legados.

A camada é projetada para falhar graciosamente: se o Postgres estiver
indisponível, `init_pool` retorna `None` e o bot continua operando com os
arquivos JSON existentes (compatibilidade durante a Fase 0).
"""

from .pool import init_pool, close_pool, get_pool
from .config import ServerConfig, load_server_config, refresh_server_config, set_config_ttl
from .global_config import GlobalConfig, load_global_config, invalidate_global_config
from .migrate import apply_migrations, import_legacy_json

__all__ = [
    "init_pool",
    "close_pool",
    "get_pool",
    "ServerConfig",
    "load_server_config",
    "refresh_server_config",
    "set_config_ttl",
    "GlobalConfig",
    "load_global_config",
    "invalidate_global_config",
    "apply_migrations",
    "import_legacy_json",
]
