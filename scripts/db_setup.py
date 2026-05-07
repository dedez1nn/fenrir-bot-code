"""Aplica migrations e importa JSONs legados manualmente.

Útil para CI, deploys e troubleshooting. Boot do bot já faz isso
automaticamente; este script existe para operações fora do bot.

Uso:
    python -m scripts.db_setup           # apply migrations + import
    python -m scripts.db_setup --no-import
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import apply_migrations, close_pool, import_legacy_json, init_pool  # noqa: E402

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main(do_import: bool) -> int:
    pool = await init_pool()
    if pool is None:
        print("ERROR: pool não inicializado (DATABASE_URL definida?)", file=sys.stderr)
        return 1
    try:
        await apply_migrations(pool)
        if do_import:
            counters = await import_legacy_json(pool)
            print(f"Importação JSON→DB: {counters}")
    finally:
        await close_pool()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-import", action="store_true", help="Pula importação JSON")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(do_import=not args.no_import)))
