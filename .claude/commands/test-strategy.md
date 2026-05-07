Create or review unit and integration tests for the Fenrir Discord bot.

- If $ARGUMENTS is provided, focus on that cog (e.g., `aventurar` → `cogs/progressao/aventurar.py`, `tests/test_aventura.py`)
- If no argument, review all existing tests for coverage gaps and quality issues

## Project test conventions (always follow these)
- Framework: `pytest` with `pytest-asyncio`, `asyncio_mode = auto`
- Mock `commands.Bot` with `MagicMock`
- Patch `tasks.loop` decorators before instantiating the cog to prevent background tasks from starting
- Use `AsyncMock` for all Discord interaction methods (`response.send_message`, `followup.send`, etc.)
- Interaction fixtures must have `channel_id = 1426205118293868748` or the command guard will reject the call
- Data files (`data/*.json`) should be mocked with `unittest.mock.patch("builtins.open", ...)` or `tmp_path` — never read/write real data files in tests

## Test areas

### 1. Command validation
For every slash command in the target cog:
- Test the happy path (valid input, correct channel, authorized user)
- Test rejection when `interaction.channel_id != 1426205118293868748` (should silently return or send an error)
- Test with invalid/boundary arguments (empty string, negative numbers, unknown item names)
- Test when a dependency cog (`bot.get_cog(...)`) returns `None`

### 2. Permission matrices
Test each command with these user states:
| State | Expected behavior |
|---|---|
| No roles | Blocked or limited functionality |
| Standard member | Base XP/coins rates |
| Premium aventureiro | 2x XP/coins multiplier applied |
| Premium lendario | 4x XP/coins multiplier applied |
| Premium mitico | 6x XP/coins multiplier applied |
| Moderator | Access to moderation commands |

### 3. Anti-spam / cooldowns
- Test that `CooldownCog.registrar_compra` blocks a second use before the cooldown expires
- Test that the cooldown correctly expires after the configured duration
- Mock `datetime.now()` to control time in cooldown tests

### 4. External API mocks
- **Mercado Pago / PIX** (`cogs/economia/pix.py`): mock `httpx.AsyncClient` or `requests.post` — test payment creation success, failure (bad token), and webhook notification handling
- **Gmail** (if used): mock `smtplib.SMTP` — test email send success and SMTP error handling
- **Riot API** (`cogs/apis/riot.py`): mock `aiohttp` or `httpx` — test 200 response parsing and 404/rate-limit handling
- **Steam / GNews**: same pattern — mock HTTP client, test response parsing

### 5. Regression tests
Check `FIX_BUGS.md` for documented bugs. For each bug:
- Write a test that would have caught the bug before the fix
- Name it `test_regression_<short_description>`
- Add a comment with one line explaining which bug it covers

## Output
- Write new test functions directly into the appropriate `tests/test_*.py` file
- Run `pytest tests/test_<target>.py -v` after writing and fix any failures
- Report: tests added, tests fixed, remaining coverage gaps
