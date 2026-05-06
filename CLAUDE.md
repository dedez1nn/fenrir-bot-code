# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run the bot:**
```bash
python main.py
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Run all tests:**
```bash
pytest
```

**Run a single test file:**
```bash
pytest tests/test_aventura.py
```

**Run a single test:**
```bash
pytest tests/test_aventura.py::TestAventuraCog::test_init
```

**Run with Docker:**
```bash
docker-compose up --build
```

## Environment Setup

Copy `.env.example` to `.env` and fill in:
- `TOKEN` — Discord bot token
- `ACCESS_TOKEN` — Mercado Pago access token

## Architecture

**Entry point:** `main.py` creates a `FenrirBot(commands.Bot)` with prefix `!` and all intents. On `setup_hook`, it auto-loads every `.py` file in `cogs/` (except `__init__.py`) and syncs slash commands. On `on_ready`, it posts/refreshes persistent embeds in fixed channels (status, colors, pix plans, tickets).

**Cog system:** Each file in `cogs/` is an independent feature module that must define `async def setup(bot)`. Cogs communicate with each other exclusively via `bot.get_cog("CogName")` — always check for `None` before calling methods on the result.

**Data persistence:** All state is stored as JSON files in `data/`. There is no database. Each cog owns its file and calls `carregar_dados()` / `salvar_dados()` directly. Key files:
- `data/user_data.json` — XP, level, title, premium plan, coins, daily streak per user
- `data/guilds_data.json` — guild membership and stats
- `data/loja_data.json` — shop items (sorted by price descending)
- `data/aventuras_data.json` — in-progress adventures per user
- `data/cooldowns_data.json` — per-user, per-item cooldown timestamps

**XP/Coins multiplier stack** (`xp.py:adicionar_xp`): Multipliers from guild level, premium plan, and the double-XP boost stack **additively** (not multiplicatively): `total = 1 + (guild−1) + (premium−1) + (dobro−1)`. Premium tiers: aventureiro=2x, lendario=4x, mitico=6x for both XP and coins.

**Shop purchase flow:** `LojaCog.comprar` → deducts coins via `FenrirCoins.remover_coins` → delegates side effects to `CompraCog.processar_compra` → `CooldownCog.registrar_compra` records the per-item cooldown. If `CompraCog` is unavailable, `LojaCog` refunds the coins.

**Hardcoded channel/guild IDs:** Channel and guild IDs are hardcoded throughout the cogs (not in config). Almost all slash commands are restricted to channel `1426205118293868748`. The server guild ID is `1426202696955986022`. The voice AFK channel `1427320869016829952` is excluded from XP gain.

**Level-up role system** (`xp.py:cargos_por_nivel`): Roles are assigned at levels 2, 5, 10, 20, 30, 40, 50. The `atualizar_cargos` method adds all eligible roles and removes ones below the current level. This system has a known bug — see `FIX_BUGS.md`.

**Tests:** Use `pytest-asyncio` with `asyncio_mode = auto`. The pattern for testing cogs is: mock `commands.Bot`, patch background `tasks.loop` decorators to prevent them from starting, and use `AsyncMock` for Discord interactions. The channel ID `1426205118293868748` must match in interaction fixtures or command guards will reject the call.
