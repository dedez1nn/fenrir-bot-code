# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fenrir-BOT is a Discord bot built with `discord.py` (slash-command style via `app_commands`). The `fenrir_security` branch is a focused security/moderation sub-bot. It runs independently as its own deployable unit on [Discloud](https://discloud.com), handling only the security-related features.

## Running the Bot

```bash
# Install dependencies (use virtualenv)
pip install -r requirements.txt

# Copy and fill in .env
cp .env.example .env
# Add your Discord bot TOKEN to .env

# Run the bot
python main.py
```

## Architecture

### Entry Point: `main.py`

`FenrirBot` extends `commands.Bot` with `command_prefix=None` (slash commands only). On startup, `setup_hook` auto-discovers and loads every `.py` file under `cogs/` as an extension, then calls `tree.sync()` to register slash commands globally. On `on_ready`, it posts a status embed to a hardcoded channel ID (`1427050535634075851`).

### Cogs Pattern

Each file under `cogs/` is a self-contained module that registers event listeners or slash commands. Every cog module must expose an `async def setup(bot)` function — this is the discord.py extension contract required for `load_extension` to work.

| Cog | Class | Purpose |
|-----|-------|---------|
| `cogs/security.py` | `AutoRemoveBots` | Listens to `on_member_join`; auto-kicks any bot that is not the bot itself |
| `cogs/block_inv.py` | `InviteBlocker` | Listens to `on_message`; detects Discord invite links via regex, resolves them via `fetch_invite`, and deletes messages pointing to foreign servers |
| `cogs/status.py` | `StatusCog` | Posts an online-status embed on startup; exposes the `/manutencao` admin-only slash command for maintenance announcements |
| `cogs/antispam.py` | `AntiSpam` | Hooks `on_message`/`on_message_edit`; runs the detection pipeline in `antispam/`, scores users, applies the progressive ladder, manages the blacklist role, and exposes `/antispam`, `/blacklist`, `/infractions` |

### Anti-spam package (`antispam/`)

Independent of `discord.py` cogs so logic can be unit-tested.

| Module | Responsibility |
|--------|----------------|
| `config.py` | `AntispamConfig` dataclass — thresholds, score weights, ladder, blacklist role name, log channel id |
| `normalizer.py` | NFKC, casefold, zero-width strip, confusables map, repeat collapse — defeats unicode/leetspeak evasion |
| `detector.py` | Pure analyzer; returns `list[Violation]` for flood, duplicate (SequenceMatcher), mention abuse, suspicious links, phishing keywords, invisible chars, caps, emoji/newline floods, edit-spam |
| `scoring.py` | Cumulative score with linear time-decay (`decay_per_minute`), persisted infraction history |
| `punisher.py` | Maps current score to ladder action (`warn` → `timeout_5` → `timeout_10` → `kick` → `ban`); auto-applies/removes the `Blacklist` role between thresholds |
| `storage.py` | Async JSON storage with `asyncio.Lock` + atomic `os.replace` write. Single file at `data/antispam.json` (gitignored) |
| `audit.py` | Posts a structured embed to the configured log channel for every detection event |

**Persistence choice:** JSON over MongoDB for this branch. Single-process bot on Discloud (500 MB RAM), low write rate (only on infractions), no need for cross-instance concurrency. Async lock + atomic rename gives durability; in-memory cache gives O(1) reads. Switching to Mongo later only requires a new `Storage` implementation with the same API (`load`, `save`, `guild`, `user`).

**Decision flow per message:**
1. Skip bots, DMs, whitelisted users, members with `manage_messages`.
2. `Detector.analyze` → list of violations + score delta.
3. `ScoreManager.add` → decays old score, adds delta, persists infraction.
4. Delete the offending message if the bot has `manage_messages`.
5. `Punisher.evaluate` → if score crossed a ladder threshold, enforce action + DM the user.
6. `Punisher.sync_blacklist_role` → add/remove the `Blacklist` role based on `blacklist_apply_score` / `blacklist_remove_score`.
7. `AuditLogger.log` → embed to log channel if configured.

**Admin commands** (require `manage_guild` / `manage_messages` / `manage_roles`):
`/antispam status`, `/antispam reset`, `/antispam whitelist`, `/antispam threshold`, `/antispam logchannel`, `/infractions`, `/blacklist add`, `/blacklist remove`.

### Key Design Details

- **No prefix commands** — all user-facing commands are slash commands (`@app_commands.command`).
- **Hardcoded channel IDs** live in `status.py` (`1427311999381147708`) and `main.py` (`1427050535634075851`). These target channels in the "Alcateia do Fenrir" server.
- **`block_inv.py` logic flow**: regex match → `fetch_invite` to resolve the code → compare `invite.guild.id != message.guild.id` → delete + DM the author. If DM fails (`discord.Forbidden`), it falls through to a channel warning that auto-deletes after 10 s.
- **Deployment** is via Discloud (`discloud.config`): `MAIN=main.py`, `RAM=500`, `AUTORESTART=false`. The bot name on Discloud is `Fenrir Security`.

## Environment Variables

Only one variable is required:

```
TOKEN=<Discord bot token>
```

## Branch Context

This repo is split across branches, each a separate deployable bot:
- `fenrir_security` — this branch; security/moderation features only
- `feature_spam` — spam-related features
- `main` — full bot with economy, guilds, raids, loja, Mercado Pago Pix integration
