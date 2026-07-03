"""Comando !config_status — diagnóstico de configuração para admins.

Mostra estado de validação de todas as features sem acessar o DB diretamente:
usa validate_all() contra o bot.config em memória.
"""

import discord
from discord.ext import commands


class ConfigCheck(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="config_status")
    @commands.has_permissions(administrator=True)
    async def config_status(self, ctx: commands.Context):
        cfg = getattr(self.bot, "config", None)
        if cfg is None:
            await ctx.send("❌ server_config não carregada (bot em modo degradado).")
            return

        try:
            from db.validators import validate_all
            all_errors = validate_all(cfg.to_dict())
        except Exception as exc:
            await ctx.send(f"❌ Erro ao rodar validação: {exc}")
            return

        ok_features = [f for f, errs in all_errors.items() if not errs]
        bad_features = {f: errs for f, errs in all_errors.items() if errs}

        embed = discord.Embed(
            title="🔍 Diagnóstico de Configuração",
            color=discord.Color.green() if not bad_features else discord.Color.orange(),
        )

        if ok_features:
            embed.add_field(
                name=f"✅ Features OK ({len(ok_features)})",
                value=", ".join(f"`{f}`" for f in sorted(ok_features)),
                inline=False,
            )

        for feature, errors in sorted(bad_features.items()):
            lines = []
            for err in errors:
                lines.append(f"**{err.get('code')}** — `{err.get('field')}`\n{err.get('message')}\n> {err.get('suggestion', '')}")
            embed.add_field(
                name=f"⚠️ {feature}",
                value="\n\n".join(lines)[:1024],
                inline=False,
            )

        if not bad_features:
            embed.description = "Todas as features estão corretamente configuradas."
        else:
            embed.description = f"{len(bad_features)} feature(s) com configuração incompleta."

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCheck(bot))
