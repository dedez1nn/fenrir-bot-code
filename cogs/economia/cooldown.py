import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from discord.ext import commands

from repositories import cooldowns as cooldowns_repo


class CooldownCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ARQUIVO_COOLDOWNS = "data/cooldowns_data.json"
        self.cooldowns: dict = {}
        self.use_db = False

        # Duração de cooldown por posição na loja (fallback JSON mode)
        self.cooldowns_itens = {
            3: 604800,   # 7 dias  - Roubo de Coins
            6: 43200,    # 12 horas - Dobro de Experiência
            8: 86400,    # 24 horas - Cores Premium
            10: 86400,   # 24 horas - Bilheteria
            11: 86400,   # 24 horas - Cor Premium
            12: 43200,   # 12 horas - Enquete
            13: 86400,   # 24 horas - Renomear Canal
            14: 21600,   # 6 horas  - Fixar Mensagem
        }

    async def cog_load(self) -> None:
        if self.bot.db is not None:
            self.use_db = True
        else:
            self.cooldowns = self.carregar_dados()

    # ── JSON helpers ──────────────────────────────────────────────────────────

    def carregar_dados(self) -> dict:
        if os.path.exists(self.ARQUIVO_COOLDOWNS):
            with open(self.ARQUIVO_COOLDOWNS, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def salvar_dados(self) -> None:
        with open(self.ARQUIVO_COOLDOWNS, "w", encoding="utf-8") as f:
            json.dump(self.cooldowns, f, indent=4)

    # ── Operações principais (async, DB ou JSON) ───────────────────────────

    async def registrar_compra(
        self,
        user_id: int,
        item_id: int,
        cooldown_secs: Optional[float] = None,
    ) -> None:
        if self.use_db and self.bot.db:
            if cooldown_secs is None:
                async with self.bot.db.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT cooldown_h FROM items WHERE id = $1", item_id
                    )
                cooldown_secs = (
                    float(row["cooldown_h"]) * 3600
                    if row and row["cooldown_h"]
                    else 0.0
                )
            if cooldown_secs <= 0:
                return
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=cooldown_secs)
            await cooldowns_repo.register(self.bot.db, user_id, item_id, expires_at)
            print(f"⏰ Cooldown DB: user={user_id} item={item_id} dur={cooldown_secs:.0f}s")
        else:
            user_str = str(user_id)
            item_str = str(item_id)
            duration = cooldown_secs or self.cooldowns_itens.get(item_id, 86400)
            self.cooldowns.setdefault(user_str, {})[item_str] = time.time() + duration
            self.salvar_dados()
            print(f"⏰ Cooldown JSON: user={user_id} item={item_id} dur={duration:.0f}s")

    async def verificar_compra(self, user_id: int, item_id: int) -> bool:
        if self.use_db and self.bot.db:
            return await cooldowns_repo.is_active(self.bot.db, user_id, item_id)

        user_str = str(user_id)
        item_str = str(item_id)
        if user_str not in self.cooldowns or item_str not in self.cooldowns[user_str]:
            return False
        tempo_fim = self.cooldowns[user_str][item_str]
        if time.time() < tempo_fim:
            return True
        del self.cooldowns[user_str][item_str]
        if not self.cooldowns[user_str]:
            del self.cooldowns[user_str]
        self.salvar_dados()
        return False

    async def obter_tempo_restante(self, user_id: int, item_id: int) -> float:
        if self.use_db and self.bot.db:
            return await cooldowns_repo.remaining_seconds(self.bot.db, user_id, item_id)

        user_str = str(user_id)
        item_str = str(item_id)
        if user_str not in self.cooldowns or item_str not in self.cooldowns[user_str]:
            return 0.0
        return max(0.0, self.cooldowns[user_str][item_str] - time.time())


async def setup(bot: commands.Bot):
    await bot.add_cog(CooldownCog(bot))
