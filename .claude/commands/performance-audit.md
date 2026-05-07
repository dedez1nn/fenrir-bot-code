Detect performance bottlenecks, asyncio misuse, and scalability issues in the Fenrir Discord bot.

- If $ARGUMENTS is provided, audit only that cog or directory
- Otherwise, audit all files under `cogs/` and `main.py`

## 1. asyncio misuse (blocking the event loop)

Search for these patterns in async functions and event handlers:

| Pattern | Problem | Fix |
|---|---|---|
| `time.sleep(n)` | Blocks entire event loop | Replace with `await asyncio.sleep(n)` |
| `open(path, ...)` inside `async def` | Blocking I/O | Use `aiofiles` or move to a sync helper called via `loop.run_in_executor` |
| `requests.get/post(...)` | Synchronous HTTP | Replace with `httpx.AsyncClient` or `aiohttp` |
| `json.load(open(...))` inline | Blocking file read | Read file in executor or at cog load time |
| CPU-bound loops without `await` | Starves other coroutines | Add `await asyncio.sleep(0)` checkpoints or offload to executor |

## 2. JSON / data persistence bottlenecks

The project stores all state in `data/*.json`. Each cog calls `carregar_dados()` / `salvar_dados()` directly. Audit for:

- **Read-on-every-call**: functions that load the entire JSON file on every command invocation when the data could be cached in a cog instance variable and reloaded only on write
- **Write-on-every-event**: `on_message` handlers that write to JSON for every message (XP gain) — check if writes can be batched or debounced
- **No error handling on file I/O**: missing `try/except` around file reads means a corrupt JSON file crashes the cog silently
- **Race conditions**: two concurrent commands writing the same file without a lock (`asyncio.Lock`) — flag any cog that shares a data file and has concurrent write paths

## 3. Cache opportunities

Flag data that is loaded repeatedly but changes infrequently:
- Shop items (`loja_data.json`) — rarely changes, could be cached in memory and refreshed only on admin command
- Guild config / level-role mappings — static between bot restarts, no need to reload from disk per command
- External API responses (Riot summoner data, Steam prices, GNews articles) — should have a TTL-based in-memory cache

For each opportunity, suggest the caching strategy (dict with timestamp, `functools.lru_cache`, or `cachetools.TTLCache`).

## 4. Excessive polling

Review all `@tasks.loop(...)` decorators:
- List each task, its interval, and what it does
- Flag tasks polling Discord API or external APIs more frequently than necessary
- Check if any polling task could be replaced by a Discord event listener (`on_member_join`, `on_reaction_add`, etc.)
- Flag tasks that do significant work on every tick without checking if work is actually needed

## 5. Shard readiness

The bot currently runs without sharding, but audit for patterns that would break under sharding:
- `bot.guilds` iterated globally in a task (would iterate all shards' guilds — fine, but note it)
- Global in-memory state (module-level dicts/lists) that would not be shared across shards
- `bot.get_guild(ID)` calls where the guild might not be on the current shard
- Event listeners that do not filter by `guild_id == 1426202696955986022` (unnecessary work for all guilds if bot ever joins others)

## 6. Memory leaks

- `discord.Message` or `discord.Member` objects stored in module-level collections without expiry
- Event listeners registered with `bot.add_listener` inside a command (registered repeatedly on each call)
- Growing dicts in cog instance variables with no eviction (e.g., cooldown maps that never clean up expired entries)

## Output format

For each finding:
```
[SEVERITY] Category — file:line
Issue: description
Impact: what degrades under load
Fix: concrete change to make
```

At the end, provide a prioritized list: fix these 3 things first for the biggest impact.
