import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import os

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
GNEWS_BASE = "https://gnews.io/api/v4"

CATEGORIAS = [
    app_commands.Choice(name="Notícias Gerais", value="general"),
    app_commands.Choice(name="Mundo", value="world"),
    app_commands.Choice(name="Brasil", value="nation"),
    app_commands.Choice(name="Negócios", value="business"),
    app_commands.Choice(name="Tecnologia", value="technology"),
    app_commands.Choice(name="Entretenimento", value="entertainment"),
    app_commands.Choice(name="Esportes", value="sports"),
    app_commands.Choice(name="Ciência", value="science"),
    app_commands.Choice(name="Saúde", value="health"),
]


class GNewsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.feature_enabled: bool = True
        self.api_key = GNEWS_API_KEY

    async def cog_load(self) -> None:
        from db.feature_config import load_feature_state_for_cog, validate_and_save_for_cog
        self.feature_enabled = await load_feature_state_for_cog(self.bot, "gnews")
        await validate_and_save_for_cog(self.bot, "gnews", self)

    async def validate_feature_config(self) -> list:
        from db.validators import validate_gnews
        cfg = getattr(self.bot, "config", None)
        return validate_gnews(cfg.to_dict() if cfg else {})

    async def reload_feature_state(self) -> None:
        from db.feature_config import load_feature_state_for_cog, validate_and_save_for_cog
        self.feature_enabled = await load_feature_state_for_cog(self.bot, "gnews")
        await validate_and_save_for_cog(self.bot, "gnews", self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.feature_enabled:
            await interaction.response.send_message(
                "❌ Os comandos de notícias não estão habilitados neste servidor.", ephemeral=True
            )
            return False
        return True

    async def _get(self, endpoint: str, params: dict) -> dict | None:
        params["token"] = self.api_key
        params.setdefault("lang", "pt")
        params.setdefault("max", 5)
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{GNEWS_BASE}/{endpoint}", params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    if resp.status == 403:
                        print("❌ GNews: API key inválida ou limite atingido")
                    else:
                        print(f"❌ GNews API {resp.status}")
                    return None
        except aiohttp.ServerTimeoutError:
            print("❌ GNews timeout")
            return None
        except Exception as e:
            print(f"❌ GNews error: {e}")
            return None

    async def _canal_invalido(self, interaction: discord.Interaction) -> bool:
        return await self.bot.guard_channel(interaction)

    def _build_embed(self, artigos: list, titulo: str) -> discord.Embed:
        embed = discord.Embed(title=f"📰 {titulo}", color=discord.Color.blue())
        for artigo in artigos[:5]:
            titulo_art = artigo["title"]
            if len(titulo_art) > 80:
                titulo_art = titulo_art[:80] + "..."
            fonte = artigo.get("source", {}).get("name", "Desconhecido")
            url = artigo.get("url", "")
            descricao = artigo.get("description") or ""
            if len(descricao) > 120:
                descricao = descricao[:120] + "..."
            valor = f"{descricao}\n🗞️ {fonte}" + (f" | [Ler mais]({url})" if url else "")
            embed.add_field(name=f"📌 {titulo_art}", value=valor, inline=False)
        return embed

    @app_commands.command(name="noticias", description="Exibe as principais notícias do momento")
    @app_commands.describe(categoria="Categoria das notícias (padrão: gerais)")
    @app_commands.choices(categoria=CATEGORIAS)
    async def noticias(
        self,
        interaction: discord.Interaction,
        categoria: app_commands.Choice[str] = None,
    ):
        if await self._canal_invalido(interaction):
            return
            return

        await interaction.response.defer()

        params = {"country": "br"}
        if categoria:
            params["topic"] = categoria.value

        data = await self._get("top-headlines", params)

        if not data or not data.get("articles"):
            await interaction.followup.send("❌ Não foi possível obter as notícias.", ephemeral=True)
            return

        titulo_categoria = categoria.name if categoria else "Principais Notícias"
        embed = self._build_embed(data["articles"], titulo_categoria)
        embed.set_footer(
            text=f"GNews.io • {data.get('totalArticles', 'N/A')} resultados disponíveis"
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="buscar-noticias", description="Busca notícias sobre um assunto específico")
    @app_commands.describe(query="Assunto que deseja buscar", em_portugues="Buscar apenas em português (padrão: Sim)")
    async def buscar_noticias(
        self,
        interaction: discord.Interaction,
        query: str,
        em_portugues: bool = True,
    ):
        if await self._canal_invalido(interaction):
            return
            return

        await interaction.response.defer()

        params: dict = {"q": query}
        if not em_portugues:
            params["lang"] = "pt"

        data = await self._get("search", params)

        if not data or not data.get("articles"):
            await interaction.followup.send(
                f"❌ Nenhuma notícia encontrada para **{query}**.", ephemeral=True
            )
            return

        embed = self._build_embed(data["articles"], f"Notícias sobre: {query}")
        embed.set_footer(
            text=f"GNews.io • {data.get('totalArticles', 'N/A')} resultados disponíveis"
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(GNewsCog(bot))
