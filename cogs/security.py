import discord
from discord.ext import commands

class AutoRemoveBots(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.feature_enabled: bool = True

    async def cog_load(self) -> None:
        if self.bot.db is not None:
            cfg = getattr(self.bot, "config", None)
            guild_id = (cfg.get("guild_id") if cfg else None)
            if guild_id:
                from db.feature_config import is_feature_enabled
                self.feature_enabled = await is_feature_enabled(self.bot.db, guild_id, "auto_remove_bots")
        from db.feature_config import validate_and_save_for_cog
        await validate_and_save_for_cog(self.bot, "auto_remove_bots", self)

    async def validate_feature_config(self) -> list:
        from db.validators import validate_auto_remove_bots
        cfg = getattr(self.bot, "config", None)
        return validate_auto_remove_bots(cfg.to_dict() if cfg else {})

    async def reload_feature_state(self) -> None:
        await self.cog_load()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not self.feature_enabled:
            return
        if member.bot:
            if member.id == self.bot.user.id:
                return

            await member.kick(reason="Bot não autorizado automaticamente removido.")

async def setup(bot):
    await bot.add_cog(AutoRemoveBots(bot))
