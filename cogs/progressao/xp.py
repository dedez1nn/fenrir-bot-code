import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import time
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont
import io
import requests
import asyncio

from repositories import users as users_repo


class RankingView(discord.ui.View):
    def __init__(self, xp_cog, page=0):
        super().__init__(timeout=60)
        self.xp_cog = xp_cog
        self.page = page
        self.ranking_data = self.get_ranking_data()
        self.users_per_page = 5
        self.total_pages = max(1, (len(self.ranking_data) + self.users_per_page - 1) // self.users_per_page)
        self.message = None

    def get_ranking_data(self):
        try:
            return sorted(
                self.xp_cog.xp_data.items(),
                key=lambda x: (x[1]["nivel"], x[1]["xp"]),
                reverse=True
            )
        except Exception as e:
            print(f"Erro ao ordenar dados: {e}")
            return []

    async def create_ranking_image(self):
        try:
            if not self.ranking_data:
                print("Nenhum dado de ranking disponível")
                return None

            width, height = 900, 700
            background_color = (20, 20, 30)
            header_color = (35, 39, 42)
            card_color = (45, 49, 54)
            border_color = (65, 65, 75)
            text_color = (255, 255, 255)
            accent_color = (255, 215, 0)
            secondary_color = (180, 180, 180)
            title_color = (100, 200, 255)
            progress_color = (76, 175, 80)

            image = Image.new('RGB', (width, height), background_color)
            draw = ImageDraw.Draw(image)

            try:
                title_font = ImageFont.truetype("arial.ttf", 36)
                rank_font = ImageFont.truetype("arial.ttf", 24)
                name_font = ImageFont.truetype("arial.ttf", 20)
                title_user_font = ImageFont.truetype("arial.ttf", 16)
                info_font = ImageFont.truetype("arial.ttf", 14)
                small_font = ImageFont.truetype("arial.ttf", 12)
            except:
                title_font = ImageFont.load_default()
                rank_font = ImageFont.load_default()
                name_font = ImageFont.load_default()
                title_user_font = ImageFont.load_default()
                info_font = ImageFont.load_default()
                small_font = ImageFont.load_default()

            header_height = 100
            draw.rectangle([0, 0, width, header_height], fill=header_color)

            for i in range(10):
                alpha = i / 10
                color = (
                    int(header_color[0] * (1 - alpha) + 25 * alpha),
                    int(header_color[1] * (1 - alpha) + 25 * alpha),
                    int(header_color[2] * (1 - alpha) + 25 * alpha)
                )
                draw.rectangle([0, header_height - i, width, header_height - i + 1], fill=color)

            title_text = "👑 RANKING DE EXPERIÊNCIA"
            draw.text((width//2, 40), title_text, fill=accent_color,
                    font=title_font, anchor="mm")

            page_text = f"Página {self.page + 1} de {self.total_pages}"
            draw.text((width//2, 75), page_text, fill=secondary_color,
                    font=info_font, anchor="mm")

            start_index = self.page * self.users_per_page
            page_data = self.ranking_data[start_index:start_index + self.users_per_page]

            y_position = 120
            card_height = 90
            card_margin = 15
            left_margin = 50
            right_margin = 50
            avatar_size = 50

            for i, (user_id, dados) in enumerate(page_data, start=start_index + 1):
                user = self.xp_cog.bot.get_user(int(user_id))
                if user:
                    xp_atual = dados["xp"]
                    nivel = dados["nivel"]
                    titulo = dados.get("titulo", "Aprendiz")
                    premium = dados.get("premium", None)
                    xp_necessario = self.xp_cog.xp_para_proximo_nivel(nivel)
                    progresso = min(xp_atual / xp_necessario, 1.0) if xp_necessario > 0 else 0

                    if i == 1:
                        rank_color = (255, 215, 0)
                        card_border_color = (255, 215, 0)
                        card_color_user = (60, 55, 45)
                    elif i == 2:
                        rank_color = (192, 192, 192)
                        card_border_color = (192, 192, 192)
                        card_color_user = (55, 55, 60)
                    elif i == 3:
                        rank_color = (205, 127, 50)
                        card_border_color = (205, 127, 50)
                        card_color_user = (60, 50, 45)
                    else:
                        rank_color = (100, 150, 255)
                        card_border_color = border_color
                        card_color_user = card_color

                    card_rect = [left_margin, y_position, width - right_margin, y_position + card_height]

                    shadow_rect = [card_rect[0] + 3, card_rect[1] + 3, card_rect[2] + 3, card_rect[3] + 3]
                    draw.rectangle(shadow_rect, fill=(10, 10, 15))

                    draw.rectangle(card_rect, fill=card_color_user, outline=card_border_color, width=3)

                    rank_x = left_margin + 40
                    rank_y = y_position + card_height // 2

                    circle_radius = 20
                    draw.ellipse([
                        rank_x - circle_radius,
                        rank_y - circle_radius,
                        rank_x + circle_radius,
                        rank_y + circle_radius
                    ], fill=rank_color)

                    rank_symbol = f"{i}"
                    draw.text((rank_x, rank_y), rank_symbol, fill=(25, 25, 35),
                            font=rank_font, anchor="mm")

                    avatar_x = left_margin + 100
                    avatar_y = y_position + card_height // 2

                    try:
                        avatar_url = user.display_avatar.url
                        response = requests.get(avatar_url, timeout=10)
                        avatar_img = Image.open(io.BytesIO(response.content))
                        avatar_img = avatar_img.resize((avatar_size, avatar_size))

                        mask = Image.new('L', (avatar_size, avatar_size), 0)
                        mask_draw = ImageDraw.Draw(mask)
                        mask_draw.ellipse([0, 0, avatar_size, avatar_size], fill=255)

                        border_size = avatar_size + 4
                        border_mask = Image.new('L', (border_size, border_size), 0)
                        border_draw = ImageDraw.Draw(border_mask)
                        border_draw.ellipse([0, 0, border_size, border_size], fill=255)

                        avatar_with_border = Image.new('RGBA', (border_size, border_size))
                        avatar_with_border.paste(avatar_img, (2, 2), mask)

                        image.paste(avatar_with_border,
                                (avatar_x - border_size//2, avatar_y - border_size//2),
                                avatar_with_border)

                    except Exception as e:
                        draw.ellipse([
                            avatar_x - avatar_size//2,
                            avatar_y - avatar_size//2,
                            avatar_x + avatar_size//2,
                            avatar_y + avatar_size//2
                        ], fill=(70, 70, 80))

                    info_x = left_margin + 140

                    nome = user.display_name
                    if len(nome) > 18:
                        nome = nome[:18] + "..."

                    draw.text((info_x, y_position + 15), nome, fill=text_color, font=name_font)

                    titulo_text = f"« {titulo} »"
                    if len(titulo) > 25:
                        titulo_text = f"« {titulo[:25]}... »"

                    draw.text((info_x, y_position + 40), titulo_text, fill=title_color, font=title_user_font)

                    level_text = f"Nível {nivel} | XP: {xp_atual:,}/{xp_necessario:,}".replace(",", ".")
                    draw.text((info_x, y_position + 60), level_text, fill=secondary_color, font=info_font)

                    bar_width = 180
                    bar_height = 12
                    bar_x = info_x + 250
                    bar_y = y_position + card_height // 2 - bar_height // 2

                    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height],
                                        radius=6, fill=(50, 50, 60))

                    progress_width = int(bar_width * progresso)
                    if progress_width > 0:
                        draw.rounded_rectangle([bar_x, bar_y, bar_x + progress_width, bar_y + bar_height],
                                            radius=6, fill=progress_color)

                    percent_text = f"{progresso*100:.1f}%"
                    percent_x = bar_x + bar_width + 100
                    percent_y = bar_y + bar_height // 2

                    draw.text((percent_x, percent_y), percent_text,
                            fill=text_color, font=info_font, anchor="lm")

                    xp_restante = xp_necessario - xp_atual
                    if xp_restante > 0:
                        progress_text = f"Faltam {xp_restante:,} XP".replace(",", ".")
                    else:
                        progress_text = "⭐ Nível Máximo!"

                    progress_text_x = percent_x
                    draw.text((progress_text_x, y_position + 60), progress_text,
                            fill=secondary_color, font=small_font, anchor="mm")

                    y_position += card_height + card_margin

            footer_height = 40
            draw.rectangle([0, height - footer_height, width, height], fill=header_color)

            footer_text = "© 2025 ALCATEIA DO FENRIR - SISTEMA DE EXPERIÊNCIA"
            draw.text((width//2, height - 20), footer_text,
                    fill=secondary_color, font=small_font, anchor="mm")

            for i in range(5):
                alpha = i / 5
                color = (
                    int(background_color[0] * (1 - alpha) + 255 * alpha),
                    int(background_color[1] * (1 - alpha) + 255 * alpha),
                    int(background_color[2] * (1 - alpha) + 255 * alpha)
                )
                draw.rectangle([0, header_height + i, width, header_height + i + 1],
                            fill=color)

            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG', optimize=True)
            img_buffer.seek(0)

            return img_buffer

        except Exception as e:
            print(f"Erro ao criar imagem do ranking: {e}")
            import traceback
            traceback.print_exc()
            return None

    def update_buttons(self):
        self.botao_anterior.disabled = self.page == 0
        self.botao_proximo.disabled = self.page >= self.total_pages - 1

    @discord.ui.button(label="◀️ Anterior", style=discord.ButtonStyle.primary)
    async def botao_anterior(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self.update_buttons()
            await self.update_ranking_message(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Próximo ▶️", style=discord.ButtonStyle.primary)
    async def botao_proximo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.total_pages - 1:
            self.page += 1
            self.update_buttons()
            await self.update_ranking_message(interaction)
        else:
            await interaction.response.defer()

    async def update_ranking_message(self, interaction: discord.Interaction):
        try:
            img_buffer = await self.create_ranking_image()
            if img_buffer:
                file = discord.File(img_buffer, filename="ranking.png")
                embed = discord.Embed(
                    title="👑 Ranking de Experiência",
                    description=f"Página {self.page + 1} de {self.total_pages}",
                    color=discord.Color.orange()
                )
                embed.set_image(url="attachment://ranking.png")
                embed.set_footer(text="© 2025 ALCATEIA DO FENRIR")

                await interaction.response.edit_message(embed=embed, view=self, attachments=[file])
            else:
                await interaction.response.send_message("❌ Erro ao gerar ranking.", ephemeral=True)
        except Exception as e:
            print(f"Erro ao atualizar ranking: {e}")
            await interaction.response.send_message("❌ Erro ao atualizar ranking.", ephemeral=True)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass


class XPCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ARQUIVO_DADOS = "data/user_data.json"
        self.user_data = self.carregar_dados()
        self.xp_data = self.user_data
        self.cooldowns = {}
        self.cooldown_segundos = 10
        self.use_db = False
        self.feature_enabled: bool = True

        self.voice_users = {}
        self.voice_xp_interval = 300
        self.voice_xp_amount = 15000

        self.xp_por_mensagem = 5000
        self.xp_por_vitoria = 10000
        self.coins_por_mensagem = 2500
        self.coins_por_voz = 7500
        self.coins_por_vitoria = 20000
        self.bonus_coins_por_nivel = 50000

        self.dobro_xp_ativos = {}

        _default_roles = {
            2: 1427356351516119180,
            5: 1427318172033351781,
            10: 1427318241197293711,
            20: 1427318396772417701,
            30: 1427318764814336213,
            40: 1427319349764423771,
            50: 1427319515548483757,
        }
        _cfg = getattr(bot, "config", None)
        _role_map = (_cfg.get("levelup_role_map") or {}) if _cfg else {}
        self.cargos_por_nivel = (
            {int(k): int(v) for k, v in _role_map.items()}
            if _role_map else _default_roles
        )

        self._restaurar_dobro_xp()
        self.voice_check_task = self.bot.loop.create_task(self.voice_xp_loop())
        self.dobro_xp_check_task = self.bot.loop.create_task(self.dobro_xp_loop())

    async def cog_load(self):
        self.use_db = self.bot.db is not None
        if self.use_db:
            try:
                rows = await users_repo.get_all(self.bot.db)
                for row in rows:
                    uid = str(row["user_id"])
                    self.user_data[uid] = users_repo.row_to_cache(row)
                self.xp_data = self.user_data
                self._restaurar_dobro_xp()
                print(f"⭐ XPCog: {len(rows)} usuários carregados do DB.")
            except Exception as e:
                print(f"❌ XPCog: erro ao carregar usuários do DB: {e}")
                self.use_db = False

        if self.bot.config:
            self.xp_por_mensagem       = self.bot.config.get("xp_por_mensagem")       or self.xp_por_mensagem
            self.xp_por_vitoria        = self.bot.config.get("xp_por_vitoria")        or self.xp_por_vitoria
            self.voice_xp_amount       = self.bot.config.get("xp_por_voz")            or self.voice_xp_amount
            self.voice_xp_interval     = self.bot.config.get("voice_xp_interval_s")   or self.voice_xp_interval
            self.bonus_coins_por_nivel = self.bot.config.get("bonus_coins_por_nivel") or self.bonus_coins_por_nivel
            self.coins_por_mensagem    = self.bot.config.get("coins_por_mensagem")    or self.coins_por_mensagem
            self.coins_por_voz         = self.bot.config.get("coins_por_voz")         or self.coins_por_voz
            self.coins_por_vitoria     = self.bot.config.get("coins_por_vitoria")     or self.coins_por_vitoria
            self.cooldown_segundos     = self.bot.config.get("xp_message_cooldown_s") or self.cooldown_segundos

        if self.bot.db is not None:
            cfg = getattr(self.bot, "config", None)
            guild_id = (cfg.get("guild_id") if cfg else None)
            if guild_id:
                from db.feature_config import is_feature_enabled
                self.feature_enabled = await is_feature_enabled(self.bot.db, guild_id, "xp")

    async def reload_feature_state(self) -> None:
        if self.bot.db is not None:
            cfg = getattr(self.bot, "config", None)
            guild_id = (cfg.get("guild_id") if cfg else None)
            if guild_id:
                from db.feature_config import is_feature_enabled
                self.feature_enabled = await is_feature_enabled(self.bot.db, guild_id, "xp")

    def _restaurar_dobro_xp(self):
        agora = time.time()
        for user_id_str, dados in self.user_data.items():
            expiracao = dados.get("dobro_expiracao")
            if expiracao:
                if expiracao > agora:
                    self.dobro_xp_ativos[user_id_str] = expiracao
                else:
                    dados["dobro"] = False
                    dados.pop("dobro_expiracao", None)

    def carregar_dados(self):
        if os.path.exists(self.ARQUIVO_DADOS):
            print("carregou os dados")
            with open(self.ARQUIVO_DADOS, "r", encoding="utf-8") as f:
                dados = json.load(f)
                for user_id, user_data in dados.items():
                    if "xp" not in user_data:
                        user_data["xp"] = 0
                    if "nivel" not in user_data:
                        user_data["nivel"] = 1
                    if "titulo" not in user_data:
                        user_data["titulo"] = "Aprendiz"
                    if "dobro" not in user_data:
                        user_data["dobro"] = False
                    if "premium" not in user_data:
                        user_data["premium"] = None
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

    def xp_para_proximo_nivel(self, nivel):
        if nivel == 1:
            return 300000
        elif nivel <= 5:
            return 500000 + (nivel * 200000)
        elif nivel <= 10:
            return 2000000 + ((nivel - 5) * 500000)
        elif nivel <= 20:
            return 5000000 + ((nivel - 10) * 1000000)
        elif nivel <= 30:
            return 15000000 + ((nivel - 20) * 3000000)
        elif nivel <= 40:
            return 45000000 + ((nivel - 30) * 5000000)
        elif nivel <= 50:
            return 100000000 + ((nivel - 40) * 10000000)
        else:
            base = 200000000
            return base * (2 ** (nivel - 50))

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

    async def _persistir_xp(self, user_id, dados: dict) -> None:
        """Persiste xp/nivel no DB ou JSON conforme o modo ativo."""
        if self.use_db:
            try:
                await users_repo.update_xp_nivel(
                    self.bot.db, int(user_id), int(dados["xp"]), int(dados["nivel"])
                )
            except Exception as e:
                print(f"❌ update_xp_nivel DB falhou: {e}")
        else:
            self.salvar_dados()

    async def adicionar_xp_sem_multiplo(self, user_id, xp_ganho, reason="Sistema"):
        user_id_str = str(user_id)
        dados = self.obter_dados_usuario(user_id_str)
        nivel_anterior = dados["nivel"]

        dados["xp"] += xp_ganho

        subiu_nivel = False
        niveis_ganhos = 0

        while dados["xp"] >= self.xp_para_proximo_nivel(dados["nivel"]):
            dados["xp"] -= self.xp_para_proximo_nivel(dados["nivel"])
            dados["nivel"] += 1
            subiu_nivel = True
            niveis_ganhos += 1

        if subiu_nivel:
            user = self.bot.get_user(int(user_id))
            if user:
                canal_xp = self.bot.get_channel(self.bot.config.get("levelup_channel_id") if self.bot.config else None)

                coins_ganhos = 0
                bonus_info = []
                for nivel in range(nivel_anterior + 1, nivel_anterior + niveis_ganhos + 1):
                    if nivel % 5 == 0:
                        bonus_coins = (nivel // 5) * self.bonus_coins_por_nivel
                        coins_ganhos += bonus_coins
                        bonus_info.append(f"Nível {nivel}: +{bonus_coins} coins")

                if coins_ganhos > 0:
                    try:
                        coins_cog = self.bot.get_cog("FenrirCoins")
                        if coins_cog:
                            await coins_cog.adicionar_coins_sem_multiplo(user_id, coins_ganhos, f"Bonus por alcançar nível {dados['nivel']}")

                            canal_log = self.bot.get_channel(self.bot.config.get("xp_log_channel_id") if self.bot.config else None)
                            if canal_log:
                                embed_log = discord.Embed(
                                    title="💰 Bonus de Coins por Level UP!",
                                    description=f"**{user.mention}** ganhou **{coins_ganhos} coins**!\n"
                                                f"**Motivo:** Subiu para nível **{dados['nivel']}**\n"
                                                f"**Detalhes:**\n" + "\n".join(bonus_info),
                                    color=discord.Color.gold(),
                                    timestamp=discord.utils.utcnow()
                                )
                                embed_log.set_thumbnail(url=user.display_avatar.url)
                                embed_log.set_footer(text=user.id)
                                await canal_log.send(embed=embed_log)

                    except Exception as e:
                        print(f"❌ Erro ao adicionar coins: {e}")

                embed = discord.Embed(
                    title="🎉 UP de nível!",
                    description=f"**Parabéns**, {user.mention}!\n"
                                f"Seu **nível** aumentou para **{dados['nivel']}**!\n"
                                f"*({reason})*",
                    color=discord.Color.yellow(),
                    timestamp=discord.utils.utcnow()
                )

                if coins_ganhos > 0:
                    embed.add_field(
                        name="💰 Bonus de Coins!",
                        value=f"**+{coins_ganhos} coins** ganhos!\n"
                            f"*{' + '.join([f'Nv{5*i}' for i in range(1, (dados['nivel']//5)+1) if 5*i > nivel_anterior and 5*i <= dados['nivel']])}*",
                        inline=False
                    )

                embed.set_thumbnail(url=user.display_avatar.url)
                embed.set_image(url="https://cdn.discordapp.com/attachments/1288876556898275328/1431319875820720190/Lobo_Cientista_e_Tubo_de_Ensaio.png?ex=68fcfc03&is=68fbaa83&hm=adb72502bfa44cda2ba75ae2b41806e46aaccca1122d4426881944550f197d3a&")

                xp_proximo = self.xp_para_proximo_nivel(dados["nivel"])
                embed.add_field(
                    name="📊 Progresso",
                    value=f"**XP Atual:** {dados['xp']}/{xp_proximo}",
                    inline=True
                )

                try:
                    if canal_xp:
                        await canal_xp.send(embed=embed)
                except Exception as e:
                    print(f"❌ Erro ao enviar mensagem de up: {e}")

                guild = self.bot.get_guild(self.bot.config.guild_id if self.bot.config else 0)
                if guild:
                    member = guild.get_member(int(user_id))
                    if member:
                        await self.atualizar_cargos(member, dados["nivel"], canal_xp)

        await self._persistir_xp(user_id, dados)
        return subiu_nivel

    async def adicionar_xp(self, user_id, xp_ganho=None, reason="Sistema"):
        user_id_str = str(user_id)
        dados = self.obter_dados_usuario(user_id_str)
        nivel_anterior = dados["nivel"]

        if xp_ganho is None:
            if "mensagem" in reason.lower():
                xp_ganho = self.xp_por_mensagem
            elif "voz" in reason.lower():
                xp_ganho = self.voice_xp_amount
            elif "vitória" in reason.lower():
                xp_ganho = self.xp_por_vitoria

        guild_cog = self.bot.get_cog("GuildSystem")
        multiplicador_guild = 1.0

        if guild_cog and "guild" in dados and dados["guild"]:
            multiplicador_guild = guild_cog.calcular_multiplicador_guild(dados["guild"])
            print(f"   Multiplicador Guild: {multiplicador_guild}x")
        else:
            print(f"   ❌ Sem guild ou GuildSystem não carregado")

        multiplicador_xp_premium, multiplicador_coins_premium = self.calcular_multiplicador_premium(user_id)
        multiplicador_dobro = 2 if self.verificar_dobro_xp(user_id) else 1

        bonus_guild_xp = multiplicador_guild - 1
        bonus_premium_xp = multiplicador_xp_premium - 1
        bonus_dobro_xp = multiplicador_dobro - 1

        multiplicador_total_xp = 1 + bonus_guild_xp + bonus_premium_xp + bonus_dobro_xp

        xp_ganho = xp_ganho * multiplicador_total_xp

        coins_por_atividade = 0
        if "mensagem" in reason.lower():
            coins_por_atividade = self.coins_por_mensagem
        elif "voz" in reason.lower():
            coins_por_atividade = self.coins_por_voz
        elif "vitória" in reason.lower():
            coins_por_atividade = self.coins_por_vitoria

        if coins_por_atividade > 0:
            coins_cog = self.bot.get_cog("FenrirCoins")
            if coins_cog:
                await coins_cog.adicionar_coins(user_id, coins_por_atividade, reason)

        dados["xp"] += xp_ganho

        subiu_nivel = False
        niveis_ganhos = 0

        while dados["xp"] >= self.xp_para_proximo_nivel(dados["nivel"]):
            dados["xp"] -= self.xp_para_proximo_nivel(dados["nivel"])
            dados["nivel"] += 1
            subiu_nivel = True
            niveis_ganhos += 1

        if subiu_nivel:
            user = self.bot.get_user(int(user_id))
            if user:
                canal_xp = self.bot.get_channel(self.bot.config.get("levelup_channel_id") if self.bot.config else None)

                coins_ganhos = 0
                bonus_info = []
                for nivel in range(nivel_anterior + 1, nivel_anterior + niveis_ganhos + 1):
                    if nivel % 5 == 0:
                        bonus_coins = (nivel // 5) * self.bonus_coins_por_nivel
                        coins_ganhos += bonus_coins
                        bonus_info.append(f"Nível {nivel}: +{bonus_coins} coins")

                if coins_ganhos > 0:
                    try:
                        coins_cog = self.bot.get_cog("FenrirCoins")
                        if coins_cog:
                            await coins_cog.adicionar_coins_sem_multiplo(user_id, coins_ganhos, f"Bonus por alcançar nível {dados['nivel']}")

                            canal_log = self.bot.get_channel(self.bot.config.get("xp_log_channel_id") if self.bot.config else None)
                            if canal_log:
                                embed_log = discord.Embed(
                                    title="💰 Bonus de Coins por Level UP!",
                                    description=f"**{user.mention}** ganhou **{coins_ganhos} coins**!\n"
                                                f"**Motivo:** Subiu para nível **{dados['nivel']}**\n"
                                                f"**Detalhes:**\n" + "\n".join(bonus_info),
                                    color=discord.Color.gold(),
                                    timestamp=discord.utils.utcnow()
                                )
                                embed_log.set_thumbnail(url=user.display_avatar.url)
                                embed_log.set_footer(text=user.id)
                                await canal_log.send(embed=embed_log)

                    except Exception as e:
                        print(f"❌ Erro ao adicionar coins: {e}")

                embed = discord.Embed(
                    title="🎉 UP de nível!",
                    description=f"**Parabéns**, {user.mention}!\n"
                                f"Seu **nível** aumentou para **{dados['nivel']}**!\n"
                                f"*({reason})*",
                    color=discord.Color.yellow(),
                    timestamp=discord.utils.utcnow()
                )

                if coins_ganhos > 0:
                    embed.add_field(
                        name="💰 Bonus de Coins!",
                        value=f"**+{coins_ganhos} coins** ganhos!\n"
                            f"*{' + '.join([f'Nv{5*i}' for i in range(1, (dados['nivel']//5)+1) if 5*i > nivel_anterior and 5*i <= dados['nivel']])}*",
                        inline=False
                    )

                embed.set_thumbnail(url=user.display_avatar.url)

                xp_proximo = self.xp_para_proximo_nivel(dados["nivel"])
                embed.add_field(
                    name="📊 Progresso",
                    value=f"**XP Atual:** {dados['xp']}/{xp_proximo}",
                    inline=True
                )

                try:
                    if canal_xp:
                        await canal_xp.send(embed=embed)
                except Exception as e:
                    print(f"❌ Erro ao enviar mensagem de up: {e}")

                guild = self.bot.get_guild(self.bot.config.guild_id if self.bot.config else 0)
                if guild:
                    member = guild.get_member(int(user_id))
                    if member:
                        await self.atualizar_cargos(member, dados["nivel"], canal_xp)

        await self._persistir_xp(user_id, dados)
        return subiu_nivel

    async def atualizar_cargos(self, member, nivel, canal_xp=None):
        try:
            cargos_para_adicionar = []
            cargos_para_remover = []

            cargo_atual = None
            nivel_atual = 0

            for nivel_requerido, cargo_id in self.cargos_por_nivel.items():
                cargo = member.guild.get_role(cargo_id)
                if not cargo:
                    print(f"❌ Cargo com ID {cargo_id} não encontrado no servidor")
                    continue

                if cargo in member.roles and nivel_requerido > nivel_atual:
                    cargo_atual = cargo
                    nivel_atual = nivel_requerido

                if nivel >= nivel_requerido:
                    if cargo not in member.roles:
                        cargos_para_adicionar.append(cargo)
                        print(f"✅ Marcado para adicionar: {cargo.name}")
                else:
                    if cargo in member.roles:
                        cargos_para_remover.append(cargo)
                        print(f"❌ Marcado para remover: {cargo.name}")

            if cargos_para_remover:
                try:
                    await member.remove_roles(*cargos_para_remover, reason=f"Progressão de Nível - {nivel}")
                    print(f"✅ Cargos removidos: {[c.name for c in cargos_para_remover]}")
                except discord.Forbidden:
                    print("❌ Sem permissão para remover cargos")
                except Exception as e:
                    print(f"❌ Erro ao remover cargos: {e}")

            if cargos_para_adicionar:
                try:
                    await member.add_roles(*cargos_para_adicionar, reason=f"XP System - Nível {nivel}")
                    print(f"✅ Cargos adicionados: {[c.name for c in cargos_para_adicionar]}")
                    for cargo in cargos_para_adicionar:
                        try:
                            embed = discord.Embed(
                                title="🏅 Novo Cargo Desbloqueado!",
                                description=f"Parabéns {member.mention}!\nVocê recebeu o cargo **{cargo.name}** por alcançar o nível {nivel}!\n"
                                            "Para garantir mais recompensas, continue interagindo em\n"
                                            "nossos canais, confira a nossa **/loja**, participe de nossos\n"
                                            "eventos e divulgue nosso servidor no **Discord!**",
                                color=discord.Color.gold(),
                                timestamp=discord.utils.utcnow()
                            )
                            embed.set_author(name=self.bot.user.name)
                            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
                            embed.set_footer(text="© 2025 ALCATEIA DO FENRIR. Todos os direitos reservados.")
                            await member.send(embed=embed)
                        except discord.Forbidden:
                            if canal_xp:
                                await canal_xp.send(f"{member.mention}, você recebeu o cargo **{cargo.name}**!")
                except discord.Forbidden:
                    print("❌ Sem permissão para adicionar cargos")
                except Exception as e:
                    print(f"❌ Erro ao adicionar cargos: {e}")

        except Exception as e:
            print(f"❌ Erro geral em atualizar_cargos: {e}")

    async def ativar_dobro_xp(self, user_id: int, duracao_horas: int) -> bool:
        try:
            user_id_str = str(user_id)
            agora = time.time()
            expiracao = agora + (duracao_horas * 3600)

            self.dobro_xp_ativos[user_id_str] = expiracao

            dados = self.obter_dados_usuario(user_id_str)
            dados["dobro"] = True
            dados["dobro_expiracao"] = expiracao

            if self.use_db:
                try:
                    expiracao_dt = datetime.fromtimestamp(expiracao, tz=timezone.utc)
                    await users_repo.set_dobro(self.bot.db, user_id, True, expiracao_dt)
                except Exception as e:
                    print(f"❌ set_dobro DB falhou: {e}")
            else:
                self.salvar_dados()

            canal_log = self.bot.get_channel(self.bot.config.get("xp_log_channel_id") if self.bot.config else None)
            user = self.bot.get_user(user_id)
            if canal_log and user:
                embed_log = discord.Embed(
                    title="🚀 Dobro de XP Ativado!",
                    description=(
                        f"**{user.mention}** ativou o **DOBRO DE XP**!\n"
                        f"**Duração:** {duracao_horas} horas\n"
                        f"**Expira:** <t:{int(expiracao)}:R>\n"
                        f"**Status:** ✅ **ATIVO**"
                    ),
                    color=discord.Color.gold(),
                    timestamp=discord.utils.utcnow()
                )
                embed_log.set_thumbnail(url=user.display_avatar.url)
                await canal_log.send(embed=embed_log)

            print(f"✅ Dobro de XP ativado para {user_id} por {duracao_horas}h (expira em {expiracao})")
            return True

        except Exception as e:
            print(f"❌ Erro ao ativar dobro de XP: {e}")
            return False

    def verificar_dobro_xp(self, user_id: int) -> bool:
        user_id_str = str(user_id)

        if user_id_str in self.dobro_xp_ativos:
            if time.time() < self.dobro_xp_ativos[user_id_str]:
                return True
            del self.dobro_xp_ativos[user_id_str]
            if user_id_str in self.user_data:
                self.user_data[user_id_str]["dobro"] = False
                self.user_data[user_id_str].pop("dobro_expiracao", None)

        return False

    async def dobro_xp_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                agora = time.time()
                expirados = []

                for user_id_str, expiracao in self.dobro_xp_ativos.items():
                    if agora >= expiracao:
                        expirados.append(user_id_str)
                        if user_id_str in self.user_data:
                            self.user_data[user_id_str]["dobro"] = False

                for user_id_str in expirados:
                    del self.dobro_xp_ativos[user_id_str]

                    if self.use_db:
                        try:
                            await users_repo.set_dobro(self.bot.db, int(user_id_str), False, None)
                        except Exception as e:
                            print(f"❌ set_dobro (expiração) DB falhou: {e}")

                    user_id = int(user_id_str)
                    user = self.bot.get_user(user_id)
                    if user:
                        try:
                            embed = discord.Embed(
                                title="⏰ Dobro de XP Expirado",
                                description="Seu **dobro de XP** acabou!\nVocê pode comprar outro na loja.",
                                color=discord.Color.orange()
                            )
                            await user.send(embed=embed)
                        except:
                            pass

                if expirados and not self.use_db:
                    self.salvar_dados()

                if expirados:
                    print(f"🔄 Dobro de XP expirado para {len(expirados)} usuários")

                await asyncio.sleep(300)

            except Exception as e:
                print(f"❌ Erro no dobro_xp_loop: {e}")
                await asyncio.sleep(60)

    async def voice_xp_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                agora = time.time()
                usuarios_que_ganharam = []
                for user_id, data in self.voice_users.items():
                    guild = self.bot.get_guild(self.bot.config.guild_id if self.bot.config else 0)
                    if guild:
                        member = guild.get_member(int(user_id))
                        if member and member.voice and member.voice.channel:
                            if member.voice.channel.id == (self.bot.config.get("afk_voice_channel_id") if self.bot.config else None):
                                continue

                    join_time = data["join_time"]
                    last_xp_time = data.get("last_xp_time", join_time)

                    if agora - last_xp_time >= self.voice_xp_interval:
                        self.voice_users[user_id]["last_xp_time"] = agora

                        user = self.bot.get_user(int(user_id))
                        if user:
                            await self.adicionar_xp(user.id, self.voice_xp_amount, "Voz no chat")
                            xp_atual = self.user_data.get(user_id, {}).get("xp", 0)
                            usuarios_que_ganharam.append((user, self.voice_xp_amount, xp_atual))

                if usuarios_que_ganharam:
                    canal_log = self.bot.get_channel(self.bot.config.get("xp_log_channel_id") if self.bot.config else None)
                    descricao_lines = []
                    for user, xp_ganho, xp_total in usuarios_que_ganharam:
                        status_dobro = " (DOBRO DE XP!)" if self.verificar_dobro_xp(user.id) else ""
                        descricao_lines.append(f"• {user.mention} ganhou {xp_ganho} XP{status_dobro} | Total: {xp_total} XP")

                    embed_log = discord.Embed(
                        title="🌟 Ganho de Experiência por Voz",
                        description="\n".join(descricao_lines),
                        color=discord.Color.dark_red(),
                        timestamp=discord.utils.utcnow()
                    )
                    embed_log.set_thumbnail(url=self.bot.user.display_avatar.url)
                    await canal_log.send(embed=embed_log)

                await asyncio.sleep(30)
            except Exception as e:
                print(f"Erro no voice_xp_loop: {e}")
                await asyncio.sleep(60)

    @commands.Cog.listener()
    async def on_member_update(self, antes: discord.Member, depois: discord.Member):
        if not antes.premium_since and depois.premium_since:
            try:
                coins_cog = self.bot.get_cog("FenrirCoins")
                if coins_cog:
                    await coins_cog.adicionar_coins(depois.id, 10000, "Boost no Servidor")
                await self.adicionar_xp(depois.id, 100, "Boost no Servidor")

                embed = discord.Embed(
                    title="💎 Obrigado pelo Boost!",
                    description=(
                        f"🎉 **Olá {depois.name}!**\n\n"
                        f"Muito obrigado por impulsionar o servidor **{depois.guild.name}**! 🚀\n\n"
                        "💖 *Seu apoio ajuda nossa comunidade a crescer e continuar incrível!*\n\n"
                        "💰 Você receberá **10.000 coins** como recompensa e 100 de Experiência.\n"
                        "🌟 Também ganhará um **cargo especial de Booster** exclusivo.\n"
                        "🎁 Além disso, **abra um ticket** para escolher **um item de até 15.000 coins gratuitamente!** 🛒\n\n"
                        "✨ Obrigado por fazer parte do nosso crescimento! 💎"
                    ),
                    color=discord.Color.purple()
                )
                embed.set_thumbnail(url=depois.display_avatar.url)
                embed.add_field(
                    name="**Data do Boost:**",
                    value=depois.premium_since.strftime("%d/%m/%Y %H:%M:%S"),
                    inline=False
                )
                embed.set_footer(text="💖 Agradecemos de coração pelo seu apoio!")

                await depois.send(embed=embed)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        if after.channel and after.channel.id == (self.bot.config.get("afk_voice_channel_id") if self.bot.config else None):
            return

        if before.channel and before.channel.id == (self.bot.config.get("afk_voice_channel_id") if self.bot.config else None):
            return

        user_id = str(member.id)
        agora = time.time()

        if after.channel and not before.channel:
            self.voice_users[user_id] = {
                "join_time": agora,
                "last_xp_time": agora,
                "channel_id": after.channel.id
            }
            print(f"🎧 {member.name} entrou no canal de voz")

        elif before.channel and not after.channel:
            if user_id in self.voice_users:
                del self.voice_users[user_id]
                print(f"🎧 {member.name} saiu do canal de voz")

        elif before.channel and after.channel and before.channel != after.channel:
            if user_id in self.voice_users:
                self.voice_users[user_id]["channel_id"] = after.channel.id
                print(f"🎧 {member.name} foi movido para outro canal")

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.feature_enabled:
            return
        if message.author.bot or not message.guild:
            return

        user_id = str(message.author.id)
        agora = time.time()

        if user_id in self.cooldowns and agora - self.cooldowns[user_id] < self.cooldown_segundos:
            return

        self.cooldowns[user_id] = agora

        await self.adicionar_xp(user_id, reason="Mensagem no chat")

        canal_log = self.bot.get_channel(self.bot.config.get("xp_log_channel_id") if self.bot.config else None)

        status_dobro = " (DOBRO DE XP ATIVO!)" if self.verificar_dobro_xp(message.author.id) else ""

        embed_log = discord.Embed(
            title="🌟 Ganho de Experiência",
            description=(
                f"**O membro {message.author.mention} ganhou XP{status_dobro}**\n"
                f"**Base:** {self.xp_por_mensagem} XP | **Motivo:** Mensagem no chat\n"
                f"**Novo XP:** {self.user_data[user_id]['xp']}"
            ),
            color=discord.Color.dark_red(),
            timestamp=discord.utils.utcnow()
        )
        embed_log.set_thumbnail(url=message.author.display_avatar.url)
        embed_log.set_footer(text=f"ID: {message.author.id}")
        await canal_log.send(embed=embed_log)

    @app_commands.command(name="xp", description="Mostra o seu XP.")
    async def xp(self, interaction: discord.Interaction, membro: discord.Member = None):
        try:
            if await self.bot.guard_channel(interaction):
                return

            await interaction.response.defer(ephemeral=True)

            membro = membro or interaction.user

            if self.use_db:
                try:
                    row = await users_repo.get_or_create(self.bot.db, membro.id)
                    dados = users_repo.row_to_cache(row)
                    self.user_data[str(membro.id)] = dados
                except Exception:
                    dados = self.user_data.get(str(membro.id), {"xp": 0, "nivel": 1, "titulo": "Aprendiz"})
            else:
                dados = self.user_data.get(str(membro.id), {"xp": 0, "nivel": 1, "titulo": "Aprendiz"})

            nivel = dados["nivel"]
            xp_atual = dados["xp"]
            xp_proximo = self.xp_para_proximo_nivel(nivel)

            embed = discord.Embed(
                title=f"📊 XP de {membro.display_name}",
                description=f"**Nível:** {nivel}\n**XP:** {xp_atual}/{xp_proximo}",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=membro.display_avatar.url)

            if "titulo" in dados:
                embed.add_field(name="🏷️ Título", value=dados["titulo"], inline=True)

            premium = dados.get("premium")
            if premium:
                multiplicador_xp, multiplicador_coins = self.calcular_multiplicador_premium(membro.id)
                embed.add_field(name="💎 Premium", value=f"{premium.title()} ({multiplicador_xp}x XP / {multiplicador_coins}x coins)", inline=True)

            if self.verificar_dobro_xp(membro.id):
                embed.add_field(name="🚀 Status", value="Dobro de XP ATIVO!", inline=True)

            if str(membro.id) in self.voice_users:
                tempo_em_voz = time.time() - self.voice_users[str(membro.id)]["join_time"]
                minutos = int(tempo_em_voz // 60)
                embed.add_field(
                    name="🎧 Tempo em Voz",
                    value=f"{minutos} minutos",
                    inline=True
                )

            try:
                canal_log = self.bot.get_channel(self.bot.config.get("xp_log_channel_id") if self.bot.config else None)
                if canal_log:
                    embed_log = discord.Embed(
                        title="🔎 Consulta de XP",
                        description=f"O membro {interaction.user.mention} consultou o XP!\nMembro consultado: {membro.mention}",
                        color=discord.Color.orange(),
                        timestamp=discord.utils.utcnow()
                    )
                    embed_log.set_thumbnail(url=membro.display_avatar.url)
                    embed_log.set_footer(text=f"ID: {membro.id}")
                    await canal_log.send(embed=embed_log)
            except Exception as log_error:
                print(f"Erro no log: {log_error}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"Erro no comando xp: {e}")
            try:
                await interaction.followup.send(
                    "❌ Ocorreu um erro ao processar o comando. Tente novamente.",
                    ephemeral=True
                )
            except:
                pass

    @app_commands.command(name="status_dobro_xp", description="Mostra status do seu dobro de XP")
    async def status_dobro_xp(self, interaction: discord.Interaction):
        try:
            if await self.bot.guard_channel(interaction):
                return

            await interaction.response.defer(ephemeral=True)

            user_id = str(interaction.user.id)

            embed = discord.Embed(
                title="🚀 Status do Dobro de XP",
                color=discord.Color.gold()
            )

            premium = self.user_data.get(user_id, {}).get("premium")
            multiplicador_xp_premium, multiplicador_coins_premium = self.calcular_multiplicador_premium(interaction.user.id)

            if self.verificar_dobro_xp(interaction.user.id):
                expiracao = self.dobro_xp_ativos.get(user_id)
                if expiracao:
                    tempo_restante = expiracao - time.time()
                    horas = int(tempo_restante // 3600)
                    minutos = int((tempo_restante % 3600) // 60)

                    guild_cog = self.bot.get_cog("GuildSystem")
                    multiplicador_guild = 1.0
                    dados_user = self.user_data.get(user_id, {})
                    if guild_cog and dados_user.get("guild"):
                        multiplicador_guild = guild_cog.calcular_multiplicador_guild(dados_user["guild"])
                    multiplicador_total = 1 + (multiplicador_guild - 1) + (multiplicador_xp_premium - 1) + 1

                    embed.description = (
                        f"✅ **DOBRO DE XP ATIVO!**\n"
                        f"**Tempo restante:** {horas}h {minutos}m\n"
                        f"**Expira:** <t:{int(expiracao)}:R>\n\n"
                        f"🎯 **Multiplicadores ativos:**\n"
                        f"• Premium: {multiplicador_xp_premium}x XP / {multiplicador_coins_premium}x coins\n"
                        f"• Dobro XP: 2x XP\n"
                        f"• **Total:** {multiplicador_total}x XP / {multiplicador_coins_premium}x coins"
                    )
                else:
                    embed.description = "✅ **DOBRO DE XP ATIVO!**\n(Duração indefinida)"
            else:
                if premium:
                    embed.description = (
                        f"❌ **Dobro de XP não está ativo**\n\n"
                        f"💎 **Seu plano {premium.title()}:** {multiplicador_xp_premium}x XP / {multiplicador_coins_premium}x coins\n\n"
                        "💎 Compre na loja para ativar o dobro de XP por 12 horas!\n"
                        "Use `/loja` para ver os itens disponíveis."
                    )
                else:
                    embed.description = (
                        "❌ **Dobro de XP não está ativo**\n\n"
                        "💎 Compre na loja para ativar o dobro de XP por 12 horas!\n"
                        "Use `/loja` para ver os itens disponíveis."
                    )

            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"Erro no comando status_dobro_xp: {e}")
            try:
                await interaction.followup.send(
                    "❌ Ocorreu um erro ao processar o comando. Tente novamente.",
                    ephemeral=True
                )
            except:
                pass

    @app_commands.command(name="set_titulo", description="Configurar título personalizado (ADM)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        membro="Membro para configurar título",
        titulo="Título personalizado"
    )
    async def set_titulo(self, interaction: discord.Interaction, membro: discord.Member, titulo: str):
        try:
            if await self.bot.guard_channel(interaction):
                return

            user_id_str = str(membro.id)

            if user_id_str not in self.user_data:
                self.user_data[user_id_str] = {
                    "xp": 0,
                    "nivel": 1,
                    "titulo": titulo,
                    "dobro": False,
                    "premium": None
                }
            else:
                self.user_data[user_id_str]["titulo"] = titulo

            if self.use_db:
                try:
                    await users_repo.set_titulo(self.bot.db, membro.id, titulo)
                except Exception as e:
                    print(f"❌ set_titulo DB falhou: {e}")
            else:
                self.salvar_dados()

            await interaction.response.send_message(
                f"✅ **Título configurado!**\n"
                f"**{membro.mention}** agora tem o título: **{titulo}**",
                ephemeral=True
            )

        except Exception as e:
            print(f"Erro no comando set_titulo: {e}")
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar o comando.",
                ephemeral=True
            )

    @app_commands.command(name="set_premium", description="Configurar plano premium para um membro (ADM)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        membro="Membro para configurar premium",
        plano="Plano premium (aventureiro, lendario, mitico)"
    )
    @app_commands.choices(plano=[
        app_commands.Choice(name="Aventureiro (2x XP/coins)", value="aventureiro"),
        app_commands.Choice(name="Lendário (4x XP/coins)", value="lendario"),
        app_commands.Choice(name="Mítico (6x XP/coins)", value="mitico"),
        app_commands.Choice(name="Remover Premium", value="none")
    ])
    async def set_premium(self, interaction: discord.Interaction, membro: discord.Member, plano: str):
        try:
            if await self.bot.guard_channel(interaction):
                return

            user_id_str = str(membro.id)
            premium_valor = None if plano == "none" else plano

            if user_id_str not in self.user_data:
                self.user_data[user_id_str] = {
                    "xp": 0,
                    "nivel": 1,
                    "titulo": "Aprendiz",
                    "dobro": False,
                    "premium": premium_valor
                }
            else:
                self.user_data[user_id_str]["premium"] = premium_valor

            if self.use_db:
                try:
                    await users_repo.set_premium(self.bot.db, membro.id, premium_valor, None)
                except Exception as e:
                    print(f"❌ set_premium DB falhou: {e}")
            else:
                self.salvar_dados()

            if plano == "none":
                await interaction.response.send_message(
                    f"✅ **Premium removido!**\n"
                    f"**{membro.mention}** não tem mais um plano premium.",
                    ephemeral=True
                )
            else:
                multiplicador_xp, multiplicador_coins = self.calcular_multiplicador_premium(membro.id)
                await interaction.response.send_message(
                    f"✅ **Plano premium configurado!**\n"
                    f"**{membro.mention}** agora tem o plano **{plano.title()}**\n"
                    f"**Multiplicadores:** {multiplicador_xp}x XP / {multiplicador_coins}x coins",
                    ephemeral=True
                )

        except Exception as e:
            print(f"Erro no comando set_premium: {e}")
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar o comando.",
                ephemeral=True
            )

    @app_commands.command(name="reset-xp-all", description="Zerar o XP de TODOS os membros (ADM)")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_xp_all(self, interaction: discord.Interaction):
        try:
            if await self.bot.guard_channel(interaction):
                return

            for user_id, dados in self.user_data.items():
                try:
                    membro = interaction.guild.get_member(int(user_id))
                    if membro:
                        for nivel_requerido, cargo_id in self.cargos_por_nivel.items():
                            if dados["nivel"] >= nivel_requerido:
                                cargo = interaction.guild.get_role(cargo_id)
                                if cargo and cargo in membro.roles:
                                    await membro.remove_roles(cargo, reason="Reset total de XP")
                except Exception as e:
                    print(f"Erro ao processar membro {user_id}: {e}")

            if self.use_db:
                try:
                    await users_repo.reset_xp_all(self.bot.db)
                except Exception as e:
                    print(f"❌ reset_xp_all DB falhou: {e}")

            self.user_data.clear()

            canal_log = self.bot.get_channel(self.bot.config.get("xp_log_channel_id") if self.bot.config else None)
            embed_log = discord.Embed(
                title="🔔 Remoção de Experiência Geral",
                description=f"\n\nO Administrador {interaction.user.mention} zerou o XP de todos!\n"
                             f"Todo o banco de dados de XP foi limpo.",
                color=discord.Color.dark_red(),
                timestamp=discord.utils.utcnow()
            )
            embed_log.set_thumbnail(url=interaction.user.display_avatar.url)
            embed_log.set_footer(text=interaction.user.id)
            await canal_log.send(embed=embed_log)

            await interaction.response.send_message(
                "✅ XP de **TODOS** os membros foi zerado!\n"
                "Todos os cargos do sistema de XP foram removidos.",
                ephemeral=True
            )

        except Exception as e:
            print(f"Erro no comando reset-xp-all: {e}")
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar o comando.",
                ephemeral=True
            )

    @app_commands.command(name="reset-xp", description="Zerar o XP do membro selecionado (ADM)")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_xp(self, interaction: discord.Interaction, membro: discord.Member):
        try:
            user_id = str(membro.id)
            if user_id in self.user_data:
                nivel_antes = self.user_data[user_id]["nivel"]
                self.user_data[user_id]["xp"] = 0
                self.user_data[user_id]["nivel"] = 1

                if self.use_db:
                    try:
                        await users_repo.reset_xp_one(self.bot.db, membro.id)
                    except Exception as e:
                        print(f"❌ reset_xp_one DB falhou: {e}")
                else:
                    self.salvar_dados()

                await interaction.response.send_message(f"✅ XP de {membro.mention} foi zerado!", ephemeral=True)

                for nivel_requerido, cargo_id in self.cargos_por_nivel.items():
                    if nivel_antes >= nivel_requerido:
                        cargo = interaction.guild.get_role(cargo_id)
                        if cargo and cargo in membro.roles:
                            await membro.remove_roles(cargo, reason="Reset de XP")

                canal_log = self.bot.get_channel(self.bot.config.get("xp_log_channel_id") if self.bot.config else None)
                embed_log = discord.Embed(
                    title="🔔 Remoção de Experiência",
                    description=f"\n\nO Administrador {interaction.user.mention}\n"
                                f"**resetou** todo o XP de {membro.mention}**\n",
                    color=discord.Color.dark_red(),
                    timestamp=discord.utils.utcnow()
                )
                embed_log.set_thumbnail(url=interaction.user.display_avatar.url)
                embed_log.set_footer(text=interaction.user.id)
                await canal_log.send(embed=embed_log)

            else:
                await interaction.response.send_message(f"{membro.mention} não possui XP registrado.", ephemeral=True)

        except Exception as e:
            print(f"Erro no comando reset-xp: {e}")
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar o comando.",
                ephemeral=True
            )

    @app_commands.command(name="retirar-xp", description="Remover XP de um membro (ADM)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        membro="Membro que terá XP removido",
        quantidade="Quantidade de XP a remover"
    )
    async def retirar_xp(self, interaction: discord.Interaction, membro: discord.Member, quantidade: int):
        try:
            if await self.bot.guard_channel(interaction):
                return

            user_id = str(membro.id)

            if user_id not in self.user_data:
                await interaction.response.send_message(f"{membro.mention} não possui XP registrado.", ephemeral=True)
                return

            if quantidade <= 0:
                await interaction.response.send_message("A quantidade deve ser maior que 0.", ephemeral=True)
                return

            dados = self.user_data[user_id]
            nivel_anterior = dados["nivel"]

            dados["xp"] -= quantidade

            while dados["xp"] < 0 and dados["nivel"] > 1:
                dados["nivel"] -= 1
                dados["xp"] += self.xp_para_proximo_nivel(dados["nivel"])

            if dados["xp"] < 0:
                dados["xp"] = 0

            if dados["nivel"] != nivel_anterior:
                await self.atualizar_cargos(membro, dados["nivel"], interaction.channel)

            await self._persistir_xp(user_id, dados)

            canal_log = self.bot.get_channel(self.bot.config.get("xp_log_channel_id") if self.bot.config else None)
            embed_log = discord.Embed(
                title="🔔 Remoção de Experiência",
                description=f"\n\nO Administrador {interaction.user.mention}\n"
                             f"retirou **{quantidade} de XP de {membro.mention}**\n"
                             f"Novo XP de {membro.name}: **{dados['xp']}**",
                color=discord.Color.dark_red(),
                timestamp=discord.utils.utcnow()
            )
            embed_log.set_thumbnail(url=interaction.user.display_avatar.url)
            embed_log.set_footer(text=interaction.user.id)
            await canal_log.send(embed=embed_log)

            await interaction.response.send_message(
                f"✅ XP removido com sucesso!\n"
                f"{membro.mention} agora está no **nível {dados['nivel']}** com **{dados['xp']} XP**.",
                ephemeral=True
            )

        except Exception as e:
            print(f"Erro no comando retirar-xp: {e}")
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar o comando.",
                ephemeral=True
            )

    @app_commands.command(name="adicionar-xp", description="Adicionar XP a um membro (ADM)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        membro="Membro que terá XP adicionado",
        quantidade="Quantidade de XP a adicionar"
    )
    async def adicionar_xp_adm(self, interaction: discord.Interaction, membro: discord.Member, quantidade: int):
        try:
            if quantidade <= 0:
                await interaction.response.send_message("❌ A quantidade deve ser maior que 0.", ephemeral=True)
                return

            user_id = str(membro.id)
            dados = self.obter_dados_usuario(user_id)
            xp_antes = dados["xp"]
            nivel_antes = dados["nivel"]

            await self.adicionar_xp_sem_multiplo(membro.id, quantidade, "Adição manual por ADM")

            await interaction.response.send_message(
                f"✅ **{quantidade} XP** adicionados a {membro.mention}!\n"
                f"**Nível:** {nivel_antes} → {dados['nivel']}\n"
                f"**XP:** {xp_antes} → {dados['xp']}",
                ephemeral=True
            )

            canal_log = self.bot.get_channel(self.bot.config.get("xp_log_channel_id") if self.bot.config else None)
            if canal_log:
                embed_log = discord.Embed(
                    title="🔔 XP Adicionado por ADM",
                    description=f"**{interaction.user.mention}** adicionou **{quantidade} XP** a {membro.mention}",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                embed_log.set_thumbnail(url=membro.display_avatar.url)
                await canal_log.send(embed=embed_log)

        except Exception as e:
            print(f"Erro no comando adicionar-xp: {e}")
            await interaction.response.send_message("❌ Ocorreu um erro ao processar o comando.", ephemeral=True)

    @app_commands.command(name="config_voz", description="Configurar XP por tempo em voz (ADM)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        intervalo="Intervalo em minutos para ganhar XP",
        xp_quantidade="Quantidade de XP a ganhar"
    )
    async def config_voz(self, interaction: discord.Interaction, intervalo: int, xp_quantidade: int):
        try:
            if await self.bot.guard_channel(interaction):
                return

            if intervalo < 1 or xp_quantidade < 1:
                await interaction.response.send_message("❌ Intervalo e XP devem ser maiores que 0.", ephemeral=True)
                return

            self.voice_xp_interval = intervalo * 60
            self.voice_xp_amount = xp_quantidade

            await interaction.response.send_message(
                f"✅ **Configuração de XP por voz atualizada!**\n"
                f"**Intervalo:** {intervalo} minutos\n"
                f"**XP ganho:** {xp_quantidade} pontos\n"
                f"**Usuários ativos em voz:** {len(self.voice_users)}",
                ephemeral=True
            )

        except Exception as e:
            print(f"Erro no comando config_voz: {e}")
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar o comando.",
                ephemeral=True
            )

    @app_commands.command(name="status_voz", description="Mostra status do sistema de voz")
    async def status_voz(self, interaction: discord.Interaction):
        try:
            if await self.bot.guard_channel(interaction):
                return

            embed = discord.Embed(
                title="🎧 Status do Sistema de Voz",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="⚙️ Configurações",
                value=f"**Intervalo:** {self.voice_xp_interval // 60} minutos\n"
                      f"**XP por intervalo:** {self.voice_xp_amount} pontos",
                inline=False
            )

            embed.add_field(
                name="📊 Estatísticas",
                value=f"**Usuários em voz:** {len(self.voice_users)}\n"
                      f"**XP total distribuído:** {sum(dados['xp'] for dados in self.user_data.values())}",
                inline=False
            )

            if self.voice_users:
                users_list = []
                for user_id, data in list(self.voice_users.items())[:5]:
                    user = self.bot.get_user(int(user_id))
                    if user:
                        tempo = int((time.time() - data['join_time']) // 60)
                        users_list.append(f"• {user.display_name} ({tempo} min)")

                embed.add_field(
                    name="👥 Usuários Ativos",
                    value="\n".join(users_list),
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"Erro no comando status_voz: {e}")
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar o comando.",
                ephemeral=True
            )

    @app_commands.command(name="ranking", description="Mostra o ranking de Experiência com imagem")
    async def ranking(self, interaction: discord.Interaction):
        try:
            if await self.bot.guard_channel(interaction):
                return

            if not self.user_data:
                await interaction.response.send_message("❌ Nenhum dado de XP encontrado.", ephemeral=True)
                return

            await interaction.response.defer(thinking=True)

            view = RankingView(self)
            img_buffer = await view.create_ranking_image()

            if img_buffer is None:
                await interaction.followup.send("❌ Erro ao gerar a imagem do ranking.", ephemeral=True)
                return

            file = discord.File(img_buffer, filename="ranking.png")
            embed = discord.Embed(
                title="👑 Ranking de Experiência",
                description=f"Página 1 de {view.total_pages}",
                color=discord.Color.orange()
            )
            embed.set_image(url="attachment://ranking.png")
            embed.set_footer(text="© 2025 ALCATEIA DO FENRIR")

            try:
                canal_log = self.bot.get_channel(self.bot.config.get("xp_log_channel_id") if self.bot.config else None)
                if canal_log:
                    embed_log = discord.Embed(
                        title="📊 Criação de Ranking",
                        description=f"\n\nO membro {interaction.user.mention} criou um ranking!\n",
                        color=discord.Color.dark_red(),
                        timestamp=discord.utils.utcnow()
                    )
                    embed_log.set_thumbnail(url=interaction.user.display_avatar.url)
                    embed_log.set_footer(text=f"User ID: {interaction.user.id}")
                    await canal_log.send(embed=embed_log)
            except Exception as log_error:
                print(f"Erro no log: {log_error}")

            view.update_buttons()
            await interaction.followup.send(embed=embed, view=view, file=file)
            view.message = await interaction.original_response()

        except Exception as e:
            print(f"Erro no comando ranking: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao gerar o ranking.", ephemeral=True)

    @commands.Cog.listener()
    async def on_cog_unload(self):
        if hasattr(self, 'voice_check_task'):
            self.voice_check_task.cancel()
        if hasattr(self, 'dobro_xp_check_task'):
            self.dobro_xp_check_task.cancel()


async def setup(bot: commands.Bot):
    await bot.add_cog(XPCog(bot))
