import time
from datetime import datetime, timezone

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import io, requests, os, json

from repositories import users as users_repo


class RankingCoinsView(discord.ui.View):
    def __init__(self, coins_cog, page=0):
        super().__init__(timeout=120)
        self.coins_cog = coins_cog
        self.page = page
        self.ranking_data = self.get_ranking_data()
        self.total_pages = (len(self.ranking_data) + 4) // 5
        self.message = None

    def get_ranking_data(self):
        return sorted(
            self.coins_cog.user_data.items(),
            key=lambda x: x[1]["coins"],
            reverse=True
        )

    async def create_ranking_image(self):
        try:
            width, height = 900, 700
            background_color = (20, 22, 30)
            card_color = (45, 48, 60)
            border_color = (70, 70, 90)
            text_color = (255, 255, 255)
            accent_color = (255, 215, 0)
            silver_color = (200, 200, 200)
            bronze_color = (205, 127, 50)
            secondary_color = (180, 180, 180)

            image = Image.new("RGBA", (width, height), background_color + (255,))
            draw = ImageDraw.Draw(image)

            decor_path = "ranking_art.png"
            if os.path.exists(decor_path):
                deco = Image.open(decor_path).convert("RGBA").resize((250, 250))
                image.alpha_composite(deco, (width - 270, height//2 - 125))

            try:
                title_font = ImageFont.truetype("arialbd.ttf", 40)
                name_font = ImageFont.truetype("arialbd.ttf", 20)
                info_font = ImageFont.truetype("arial.ttf", 16)
            except:
                title_font = name_font = info_font = ImageFont.load_default()

            draw.text((width//2, 60), "🏆 RANKING DE COINS 💰", fill=accent_color, font=title_font, anchor="mm")
            draw.text((width//2, 100), f"Página {self.page + 1} de {self.total_pages}", fill=secondary_color, font=info_font, anchor="mm")

            start_index = self.page * 5
            page_data = self.ranking_data[start_index:start_index + 5]

            y = 150
            card_height = 90
            margin_x = 100
            avatar_size = 70

            async with aiohttp.ClientSession() as session:
                for i, (user_id, dados) in enumerate(page_data, start=start_index + 1):
                    user = self.coins_cog.bot.get_user(int(user_id))
                    if not user:
                        continue

                    coins = dados.get("coins", 0)
                    total_ganho = dados.get("total_ganho", 0)

                    if i == 1:
                        rank_color, rank_symbol = accent_color, "🥇"
                    elif i == 2:
                        rank_color, rank_symbol = silver_color, "🥈"
                    elif i == 3:
                        rank_color, rank_symbol = bronze_color, "🥉"
                    else:
                        rank_color, rank_symbol = (140, 140, 255), f"#{i}"

                    shadow = Image.new("RGBA", (width, card_height+10), (0, 0, 0, 0))
                    shadow_draw = ImageDraw.Draw(shadow)
                    shadow_draw.rectangle([margin_x, 5, width - margin_x, card_height+5], fill=(0, 0, 0, 90))
                    image.alpha_composite(shadow, (0, y - 5))

                    draw.rectangle([margin_x, y, width - margin_x, y + card_height], fill=card_color, outline=border_color, width=2)

                    draw.text((margin_x + 30, y + card_height//2), rank_symbol, fill=rank_color, font=name_font, anchor="lm")

                    avatar_x = margin_x + 90
                    avatar_y = y + card_height // 2
                    try:
                        async with session.get(user.display_avatar.url) as resp:
                            if resp.status == 200:
                                avatar_bytes = await resp.read()
                                avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((avatar_size, avatar_size))
                                mask = Image.new("L", (avatar_size, avatar_size), 0)
                                mask_draw = ImageDraw.Draw(mask)
                                mask_draw.ellipse([0, 0, avatar_size, avatar_size], fill=255)
                                avatar_circle = Image.new("RGBA", (avatar_size, avatar_size))
                                avatar_circle.paste(avatar_img, (0, 0), mask)
                                image.alpha_composite(avatar_circle, (avatar_x - avatar_size//2, avatar_y - avatar_size//2))
                            else:
                                raise ValueError("avatar não carregado")
                    except:
                        draw.ellipse([avatar_x - 35, avatar_y - 35, avatar_x + 35, avatar_y + 35], fill=(60, 60, 70))

                    name_x = avatar_x + 60
                    nome = user.display_name[:18] + ("..." if len(user.display_name) > 18 else "")
                    draw.text((name_x, y + 25), nome, fill=text_color, font=name_font)
                    draw.text((name_x, y + 55), f"💰 {coins} coins", fill=accent_color, font=info_font)
                    draw.text((width - margin_x - 180, y + 55), f"Total ganho: {total_ganho}", fill=secondary_color, font=info_font)

                    y += card_height + 20

            footer = "© 2025 ALCATEIA DO FENRIR"
            draw.text((width//2, height - 30), footer, fill=secondary_color, font=info_font, anchor="mm")

            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer

        except Exception as e:
            print(f"Erro ao criar imagem de ranking: {e}")
            return None

    def update_buttons(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.label == "◀️ Anterior":
                    child.disabled = self.page == 0
                elif child.label == "Próximo ▶️":
                    child.disabled = self.page >= self.total_pages - 1

    @discord.ui.button(label="◀️ Anterior", style=discord.ButtonStyle.secondary)
    async def botao_anterior(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self.update_buttons()
            await interaction.response.defer()
            await self.update_ranking_message(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Próximo ▶️", style=discord.ButtonStyle.secondary)
    async def botao_proximo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.total_pages - 1:
            self.page += 1
            self.update_buttons()
            await interaction.response.defer()
            await self.update_ranking_message(interaction)
        else:
            await interaction.response.defer()

    async def update_ranking_message(self, interaction: discord.Interaction):
        try:
            img_buffer = await self.create_ranking_image()
            if img_buffer:
                file = discord.File(img_buffer, filename="ranking_coins.png")
                embed = discord.Embed(
                    title="🏆 Ranking de Coins",
                    description=f"Página {self.page + 1} de {self.total_pages}",
                    color=discord.Color.gold()
                )
                embed.set_image(url="attachment://ranking_coins.png")
                embed.set_footer(text="© 2025 ALCATEIA DO FENRIR")
                await interaction.edit_original_response(embed=embed, view=self, attachments=[file])
            else:
                await interaction.edit_original_response(content="❌ Erro ao gerar o ranking de coins.", embed=None, attachments=[])
        except Exception as e:
            print(f"Erro ao atualizar ranking de coins: {e}")
            await interaction.edit_original_response(content="❌ Erro ao atualizar ranking.", embed=None, attachments=[])

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass


class FenrirCoins(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ARQUIVO_DADOS = "data/user_data.json"
        self.user_data = self.carregar_dados()
        self.cooldowns = {}
        self.use_db = False

        self.coins_por_mensagem = 5000
        self.cooldown_mensagem = 180
        self.coins_por_voz = 15000
        self.daily_coins = 10000
        self.streak_bonus = 10000
        self.feature_enabled: bool = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.feature_enabled:
            await interaction.response.send_message(
                "❌ O sistema de economia não está habilitado neste servidor.", ephemeral=True
            )
            return False
        return True

    async def cog_load(self):
        self.use_db = self.bot.db is not None
        if self.use_db:
            try:
                rows = await users_repo.get_all(self.bot.db)
                for row in rows:
                    uid = str(row["user_id"])
                    self.user_data[uid] = users_repo.row_to_cache(row)
                print(f"💰 FenrirCoins: {len(rows)} usuários carregados do DB.")
            except Exception as e:
                print(f"❌ FenrirCoins: erro ao carregar usuários do DB: {e}")
                self.use_db = False

        if self.bot.config:
            self.coins_por_mensagem = self.bot.config.get("coins_por_mensagem")        or self.coins_por_mensagem
            self.cooldown_mensagem  = self.bot.config.get("coins_message_cooldown_s")  or self.cooldown_mensagem
            self.coins_por_voz      = self.bot.config.get("coins_por_voz")             or self.coins_por_voz
            self.daily_coins        = self.bot.config.get("daily_coins")               or self.daily_coins
            self.streak_bonus       = self.bot.config.get("daily_streak_bonus")        or self.streak_bonus

        from db.feature_config import load_feature_state_for_cog
        self.feature_enabled = await load_feature_state_for_cog(self.bot, "economy")

    async def reload_feature_state(self) -> None:
        from db.feature_config import load_feature_state_for_cog
        self.feature_enabled = await load_feature_state_for_cog(self.bot, "economy")

    def carregar_dados(self):
        if os.path.exists(self.ARQUIVO_DADOS):
            with open(self.ARQUIVO_DADOS, "r", encoding="utf-8") as f:
                dados = json.load(f)
                for user_id, user_data in dados.items():
                    if "coins" not in user_data:
                        user_data["coins"] = 0
                    if "daily_streak" not in user_data:
                        user_data["daily_streak"] = 0
                    if "last_daily" not in user_data:
                        user_data["last_daily"] = None
                    if "total_ganho" not in user_data:
                        user_data["total_ganho"] = 0
                return dados
        return {}

    def salvar_dados(self):
        if self.use_db:
            return
        with open(self.ARQUIVO_DADOS, "w", encoding="utf-8") as f:
            json.dump(self.user_data, f, indent=4)

    def obter_dados_usuario(self, user_id):
        user_id_str = str(user_id)
        if user_id_str not in self.user_data:
            self.user_data[user_id_str] = {
                "xp": 0,
                "nivel": 1,
                "titulo": "Aprendiz",
                "dobro": False,
                "premium": None,
                "coins": 0,
                "daily_streak": 0,
                "last_daily": None,
                "total_ganho": 0
            }
        return self.user_data[user_id_str]

    async def obter_coins(self, user_id: int) -> int:
        dados = self.obter_dados_usuario(user_id)
        return dados["coins"]

    def calcular_multiplicador_premium(self, user_id: int) -> tuple:
        user_id_str = str(user_id)
        if user_id_str not in self.user_data:
            return 1, 1

        premium = self.user_data[user_id_str].get("premium")

        multiplicadores = {
            "aventureiro": (2, 2),
            "lendario": (4, 4),
            "mitico": (6, 6)
        }

        return multiplicadores.get(premium, (1, 1))

    async def adicionar_coins_sem_multiplo(self, user_id, quantidade, motivo=""):
        user_id_str = str(user_id)
        dados = self.obter_dados_usuario(user_id_str)

        if self.use_db:
            try:
                row = await users_repo.add_coins(self.bot.db, int(user_id), int(quantidade))
                dados["coins"] = row["coins"]
                dados["total_ganho"] = row["total_ganho"]
            except Exception as e:
                print(f"❌ add_coins DB falhou, usando cache: {e}")
                dados["coins"] += quantidade
                dados["total_ganho"] += quantidade
        else:
            dados["coins"] += quantidade
            dados["total_ganho"] += quantidade
            self.salvar_dados()

        await self.registrar_transacao(user_id, quantidade, motivo)
        await self.enviar_log(user_id, "Adição de Coins (Sem Multiplicador)",
                            f"**Ação:** Adicionou {quantidade} coins\n"
                            f"**Motivo:** {motivo}",
                            discord.Color.green())
        print(f"💰 +{quantidade} coins para {user_id} ({motivo}) - SEM MULTIPLICADOR")

    async def adicionar_coins(self, user_id, quantidade, motivo=""):
        user_id_str = str(user_id)
        dados = self.obter_dados_usuario(user_id_str)

        if any(termo in motivo.lower() for termo in ["mensagem", "voz", "vitória", "daily", "bonus"]):
            guild_cog = self.bot.get_cog("GuildSystem")
            multiplicador_guild = 1.0

            if guild_cog and "guild" in dados and dados["guild"]:
                multiplicador_guild = guild_cog.calcular_multiplicador_guild(dados["guild"])

            _, multiplicador_coins_premium = self.calcular_multiplicador_premium(user_id)

            bonus_guild = multiplicador_guild - 1
            bonus_premium = multiplicador_coins_premium - 1

            multiplicador_total = 1 + bonus_guild + bonus_premium
            quantidade = quantidade * multiplicador_total

        if self.use_db:
            try:
                row = await users_repo.add_coins(self.bot.db, int(user_id), int(quantidade))
                dados["coins"] = row["coins"]
                dados["total_ganho"] = row["total_ganho"]
            except Exception as e:
                print(f"❌ add_coins DB falhou, usando cache: {e}")
                dados["coins"] += quantidade
                dados["total_ganho"] += quantidade
        else:
            dados["coins"] += quantidade
            dados["total_ganho"] += quantidade
            self.salvar_dados()

        await self.registrar_transacao(user_id, quantidade, motivo)
        await self.enviar_log(user_id, "Adição de Coins",
                            f"**Ação:** Adicionou {quantidade} coins\n"
                            f"**Motivo:** {motivo}",
                            discord.Color.green())
        print(f"💰 +{quantidade} coins para {user_id} ({motivo})")

    async def registrar_transacao(self, user_id: int, quantidade: int, motivo: str):
        try:
            canal_log = self.bot.get_channel(self.bot.config.get("coins_log_channel_id") if self.bot.config else None)
            if canal_log:
                user = self.bot.get_user(user_id)
                if user:
                    embed = discord.Embed(
                        title="💰 Transação de Coins",
                        description=(
                            f"**Usuário:** {user.mention} (`{user_id}`)\n"
                            f"**Valor:** {quantidade:+} coins\n"
                            f"**Motivo:** {motivo}\n"
                            f"**Data:** {discord.utils.format_dt(discord.utils.utcnow(), 'F')}"
                        ),
                        color=discord.Color.green() if quantidade > 0 else discord.Color.red()
                    )
                    await canal_log.send(embed=embed)
        except Exception as e:
            print(f"❌ Erro ao registrar transação: {e}")

    async def remover_coins(self, user_id: int, quantidade: int, motivo: str = "Sistema"):
        user_id_str = str(user_id)
        dados = self.obter_dados_usuario(user_id_str)

        if self.use_db:
            try:
                row = await users_repo.remove_coins(self.bot.db, int(user_id), int(quantidade))
                dados["coins"] = row["coins"]
            except Exception as e:
                print(f"❌ remove_coins DB falhou, usando cache: {e}")
                dados["coins"] = max(0, dados["coins"] - quantidade)
        else:
            coins_atuais = dados["coins"]
            dados["coins"] = max(0, coins_atuais - quantidade)
            self.salvar_dados()

        await self.registrar_transacao(user_id, -quantidade, motivo)

    async def enviar_log(self, user_id, acao, descricao, cor=discord.Color.dark_red()):
        try:
            canal_log = self.bot.get_channel(self.bot.config.get("coins_log_channel_id") if self.bot.config else None)
            if canal_log:
                user = self.bot.get_user(int(user_id))
                user_mention = user.mention if user else f"Usuário {user_id}"

                embed_log = discord.Embed(
                    title=f"💰 {acao}",
                    description=f"{descricao}\n\n**Usuário:** {user_mention}",
                    color=cor,
                    timestamp=discord.utils.utcnow()
                )
                if user:
                    embed_log.set_thumbnail(url=user.display_avatar.url)
                embed_log.set_footer(text=f"ID: {user_id}")
                await canal_log.send(embed=embed_log)
        except Exception as e:
            print(f"❌ Erro ao enviar log: {e}")

    @app_commands.command(name="coins", description="Ver suas coins ou de outro usuário")
    async def coins(self, interaction: discord.Interaction, membro: discord.Member = None):
        if await self.bot.guard_channel(interaction):
            return

        membro = membro or interaction.user

        if self.use_db:
            try:
                row = await users_repo.get_or_create(self.bot.db, membro.id)
                dados = users_repo.row_to_cache(row)
                self.user_data[str(membro.id)] = dados
            except Exception:
                dados = self.obter_dados_usuario(membro.id)
        else:
            dados = self.obter_dados_usuario(membro.id)

        embed = discord.Embed(
            title=f"💰 Carteira de {membro.display_name}",
            color=discord.Color.gold()
        )
        embed.add_field(name="💎 Coins", value=f"`{dados['coins']}`", inline=True)
        embed.add_field(name="🔥 Streak Diário", value=f"`{dados['daily_streak']} dias`", inline=True)
        embed.add_field(name="🏆 Total Ganho", value=f"`{dados['total_ganho']}`", inline=True)
        embed.set_thumbnail(url=membro.display_avatar.url)

        premium = dados.get("premium")
        if premium:
            multiplicador_xp, multiplicador_coins = self.calcular_multiplicador_premium(membro.id)
            embed.add_field(name="💎 Premium", value=f"{premium.title()} ({multiplicador_xp}x XP / {multiplicador_coins}x coins)", inline=False)

        await interaction.response.send_message(embed=embed)

        if membro.id == interaction.user.id:
            await self.enviar_log(
                interaction.user.id,
                "Consulta de Saldo",
                f"**Ação:** Consultou próprio saldo\n**Saldo:** {dados['coins']} coins"
            )
        else:
            await self.enviar_log(
                interaction.user.id,
                "Consulta de Saldo",
                f"**Ação:** Consultou saldo de {membro.mention}\n**Saldo:** {dados['coins']} coins"
            )

    @app_commands.command(name="daily", description="Resgatar coins diárias")
    async def daily(self, interaction: discord.Interaction):
        if await self.bot.guard_channel(interaction):
            return

        user_id = interaction.user.id
        dados = self.obter_dados_usuario(user_id)
        agora = time.time()

        if dados["last_daily"] and (agora - dados["last_daily"]) < 86400:
            tempo_restante = 86400 - (agora - dados["last_daily"])
            horas = int(tempo_restante // 3600)
            minutos = int((tempo_restante % 3600) // 60)

            await interaction.response.send_message(
                f"⏰ Você já resgatou suas coins hoje!\n"
                f"Volte em **{horas}h {minutos}m**",
                ephemeral=True
            )
            await self.enviar_log(
                interaction.user.id,
                "Tentativa de Daily",
                f"**Ação:** Tentou resgatar daily em cooldown\n**Tempo restante:** {horas}h {minutos}m",
                discord.Color.orange()
            )
            return

        streak = dados["daily_streak"]
        recompensa_base = self.daily_coins + (streak * self.streak_bonus)

        guild_cog = self.bot.get_cog("GuildSystem")
        multiplicador_guild = 1.0
        if guild_cog and dados.get("guild"):
            multiplicador_guild = guild_cog.calcular_multiplicador_guild(dados["guild"])

        _, multiplicador_coins_premium = self.calcular_multiplicador_premium(user_id)
        multiplicador_total = 1 + (multiplicador_guild - 1) + (multiplicador_coins_premium - 1)
        recompensa_final = int(recompensa_base * multiplicador_total)

        if self.use_db:
            try:
                agora_dt = datetime.fromtimestamp(agora, tz=timezone.utc)
                row = await users_repo.update_daily(
                    self.bot.db, user_id, recompensa_final, streak + 1, agora_dt
                )
                dados["daily_streak"] = row["daily_streak"]
                dados["last_daily"] = row["last_daily"].timestamp() if row.get("last_daily") else None
                dados["coins"] = row["coins"]
                dados["total_ganho"] = row["total_ganho"]
            except Exception as e:
                print(f"❌ update_daily DB falhou, usando JSON: {e}")
                dados["daily_streak"] = streak + 1
                dados["last_daily"] = agora
                dados["coins"] += recompensa_final
                dados["total_ganho"] += recompensa_final
                self.salvar_dados()
        else:
            dados["daily_streak"] = streak + 1
            dados["last_daily"] = agora
            dados["coins"] += recompensa_final
            dados["total_ganho"] += recompensa_final
            self.salvar_dados()

        embed = discord.Embed(
            title="🎁 Recompensa Diária Resgatada!",
            description=f"**+{recompensa_final} coins** adicionados à sua carteira!",
            color=discord.Color.green()
        )
        embed.add_field(name="🔥 Sequência", value=f"{dados['daily_streak']} dias", inline=True)

        proxima_recompensa = self.daily_coins + (dados['daily_streak'] * self.streak_bonus)
        proxima_recompensa_final = int(proxima_recompensa * multiplicador_total)
        embed.add_field(name="💰 Próximo Daily", value=f"+{proxima_recompensa_final} coins", inline=True)

        if multiplicador_total > 1:
            embed.add_field(name="⚡ Multiplicador Total", value=f"{multiplicador_total:.1f}x", inline=True)

        embed.set_footer(text="Volte amanhã para continuar sua sequência!")

        await interaction.response.send_message(embed=embed)
        await self.enviar_log(
            interaction.user.id,
            "Daily Resgatado",
            f"**Ação:** Resgatou daily com sucesso\n**Recompensa:** {recompensa_final} coins\n**Streak:** {dados['daily_streak']} dias\n**Multiplicador Total:** {multiplicador_total:.1f}x",
            discord.Color.green()
        )

    @app_commands.command(name="transferir", description="Transferir coins para outro usuário")
    @app_commands.describe(
        membro="Usuário para transferir",
        quantidade="Quantidade de coins"
    )
    async def transferir(self, interaction: discord.Interaction, membro: discord.Member, quantidade: int):
        if await self.bot.guard_channel(interaction):
            return

        if quantidade <= 0:
            await interaction.response.send_message("❌ Quantidade deve ser maior que 0!", ephemeral=True)
            return

        if membro.bot:
            await interaction.response.send_message("❌ Não pode transferir para bots!", ephemeral=True)
            return

        if membro.id == interaction.user.id:
            await interaction.response.send_message("❌ Não pode transferir para si mesmo!", ephemeral=True)
            return

        dados_remetente = self.obter_dados_usuario(interaction.user.id)
        saldo_anterior_remetente = dados_remetente["coins"]

        if dados_remetente["coins"] < quantidade:
            await interaction.response.send_message(
                f"❌ Saldo insuficiente! Você tem {dados_remetente['coins']} coins",
                ephemeral=True
            )
            await self.enviar_log(
                interaction.user.id,
                "Transferência Falhou",
                f"**Ação:** Tentou transferir {quantidade} coins para {membro.mention}\n**Motivo:** Saldo insuficiente\n**Saldo atual:** {dados_remetente['coins']} coins",
                discord.Color.red()
            )
            return

        dados_destino = self.obter_dados_usuario(membro.id)
        saldo_anterior_destino = dados_destino["coins"]

        if self.use_db:
            try:
                s_row, r_row = await users_repo.transfer(
                    self.bot.db, interaction.user.id, membro.id, quantidade
                )
                dados_remetente["coins"] = s_row["coins"]
                dados_destino["coins"] = r_row["coins"]
                dados_destino["total_ganho"] = r_row["total_ganho"]
            except ValueError:
                await interaction.response.send_message(
                    f"❌ Saldo insuficiente! Você tem {dados_remetente['coins']} coins",
                    ephemeral=True
                )
                return
            except Exception as e:
                print(f"❌ transfer DB falhou, usando JSON: {e}")
                dados_remetente["coins"] -= quantidade
                dados_destino["coins"] += quantidade
                dados_destino["total_ganho"] = dados_destino.get("total_ganho", 0) + quantidade
                self.salvar_dados()
        else:
            dados_remetente["coins"] -= quantidade
            dados_destino["coins"] += quantidade
            dados_destino["total_ganho"] = dados_destino.get("total_ganho", 0) + quantidade
            self.salvar_dados()

        embed = discord.Embed(
            title="✅ Transferência Realizada!",
            description=f"**{quantidade} coins** transferidos para {membro.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Seu saldo atual", value=f"`{dados_remetente['coins']} coins`", inline=True)

        await interaction.response.send_message(embed=embed)
        await self.enviar_log(
            interaction.user.id,
            "Transferência Realizada",
            f"**Ação:** Transferiu {quantidade} coins para {membro.mention}\n"
            f"**Saldo anterior remetente:** {saldo_anterior_remetente} coins\n"
            f"**Saldo atual remetente:** {dados_remetente['coins']} coins\n"
            f"**Saldo anterior destinatário:** {saldo_anterior_destino} coins\n"
            f"**Saldo atual destinatário:** {dados_destino['coins']} coins",
            discord.Color.green()
        )

    @app_commands.command(name="ranking_coins", description="Exibe o Ranking de Coins do Servidor.")
    async def ranking_coins(self, interaction: discord.Interaction):
        if await self.bot.guard_channel(interaction):
            return
        await interaction.response.defer(thinking=True)

        view = RankingCoinsView(self)

        img_buffer = await view.create_ranking_image()
        if not img_buffer:
            await interaction.followup.send("❌ Erro ao gerar a imagem do ranking.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏆 Ranking de Coins",
            description=f"Página 1 de {view.total_pages}",
            color=discord.Color.gold()
        )
        embed.set_footer(text="© 2025 ALCATEIA DO FENRIR")

        file = discord.File(img_buffer, filename="ranking_coins.png")
        await interaction.followup.send(embed=embed, file=file, view=view)
        sent_message = await interaction.original_response()
        view.message = sent_message

    @app_commands.command(name="adicionar_coins", description="Adicionar coins a um usuário (ADM)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        membro="Usuário para adicionar coins",
        quantidade="Quantidade de coins"
    )
    async def adicionar_coins_adm(self, interaction: discord.Interaction, membro: discord.Member, quantidade: int):
        if quantidade <= 0:
            await interaction.response.send_message("❌ Quantidade deve ser maior que 0!", ephemeral=True)
            return

        dados = self.obter_dados_usuario(membro.id)
        saldo_anterior = dados["coins"]

        if self.use_db:
            try:
                row = await users_repo.add_coins(self.bot.db, membro.id, quantidade)
                dados["coins"] = row["coins"]
                dados["total_ganho"] = row["total_ganho"]
            except Exception as e:
                print(f"❌ add_coins_adm DB falhou: {e}")
                dados["coins"] += quantidade
                dados["total_ganho"] += quantidade
        else:
            dados["coins"] += quantidade
            dados["total_ganho"] += quantidade
            self.salvar_dados()

        embed = discord.Embed(
            title="✅ Coins Adicionadas!",
            description=f"**+{quantidade} coins** adicionados para {membro.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Saldo anterior", value=f"`{saldo_anterior} coins`", inline=True)
        embed.add_field(name="Saldo atual", value=f"`{dados['coins']} coins`", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.enviar_log(
            interaction.user.id,
            "Admin - Coins Adicionadas",
            f"**Ação:** Adicionou {quantidade} coins para {membro.mention}\n"
            f"**Saldo anterior:** {saldo_anterior} coins\n"
            f"**Saldo atual:** {dados['coins']} coins",
            discord.Color.gold()
        )

    @app_commands.command(name="remover_coins", description="Remover coins de um usuário (ADM)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        membro="Usuário para remover coins",
        quantidade="Quantidade de coins"
    )
    async def remover_coins_adm(self, interaction: discord.Interaction, membro: discord.Member, quantidade: int):
        if quantidade <= 0:
            await interaction.response.send_message("❌ Quantidade deve ser maior que 0!", ephemeral=True)
            return

        dados = self.obter_dados_usuario(membro.id)
        saldo_anterior = dados["coins"]

        if dados["coins"] < quantidade:
            await interaction.response.send_message(
                f"❌ Saldo insuficiente! {membro.mention} tem apenas {dados['coins']} coins",
                ephemeral=True
            )
            return

        if self.use_db:
            try:
                row = await users_repo.remove_coins(self.bot.db, membro.id, quantidade)
                dados["coins"] = row["coins"]
            except Exception as e:
                print(f"❌ remove_coins_adm DB falhou: {e}")
                dados["coins"] -= quantidade
        else:
            dados["coins"] -= quantidade
            self.salvar_dados()

        embed = discord.Embed(
            title="✅ Coins Removidas!",
            description=f"**-{quantidade} coins** removidos de {membro.mention}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Saldo anterior", value=f"`{saldo_anterior} coins`", inline=True)
        embed.add_field(name="Saldo atual", value=f"`{dados['coins']} coins`", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.enviar_log(
            interaction.user.id,
            "Admin - Coins Removidas",
            f"**Ação:** Removeu {quantidade} coins de {membro.mention}\n"
            f"**Saldo anterior:** {saldo_anterior} coins\n"
            f"**Saldo atual:** {dados['coins']} coins",
            discord.Color.orange()
        )

    @adicionar_coins_adm.error
    @remover_coins_adm.error
    async def comandos_adm_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você não tem permissão de administrador para usar este comando.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(FenrirCoins(bot))
