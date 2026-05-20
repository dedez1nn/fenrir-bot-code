from discord.ext import tasks
import discord
from discord import app_commands
from discord.ext import commands
import mercadopago
import base64
from io import BytesIO
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import os
load_dotenv()

from repositories import users as users_repo
from repositories import premium as premium_repo

log = logging.getLogger(__name__)

TOKEN = os.getenv("ACCESS_TOKEN")


class PixCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mp_sdk = mercadopago.SDK(TOKEN)
        self.use_db = False
        self.feature_enabled: bool = True
        self.planos = {
            "aventureiro": 3.99,
            "lendario": 7.99,
            "mitico": 13.99
        }
        self.cargos = {
            "aventureiro": 1430230150359945306,
            "lendario": 1429546091199729704,
            "mitico": 1428728597501444186
        }
        self.recompensas = {
            "aventureiro": {"coins": 30000, "xp": 25000},
            "lendario": {"coins": 60000, "xp": 50000},
            "mitico": {"coins": 120000, "xp": 100000}
        }
        
        self.emoji_aventureiro = None
        self.emoji_lendario = None
        self.emoji_mitico = None
        self.emoji_controle = None
        self.emoji_selecao = None
        self.emoji_money_bag = None
        self.emoji_presentinho = None
        self.emoji_pix = None
        self.emoji_verify = None
        self.emoji_voltar = None
        self.emoji_timer = None
        
        self.verificar_premium_loop.start()

    async def cog_load(self):
        self.use_db = self.bot.db is not None
        if self.bot.db is not None:
            cfg = getattr(self.bot, "config", None)
            guild_id = (cfg.get("guild_id") if cfg else None)
            if guild_id:
                from db.feature_config import is_feature_enabled
                self.feature_enabled = await is_feature_enabled(self.bot.db, guild_id, "premium")
        if self.use_db:
            try:
                plans = await premium_repo.get_all(self.bot.db)
                if plans:
                    self.planos    = {p["plan_key"]: float(p["price_brl"]) for p in plans if p["price_brl"] is not None}
                    self.cargos    = {p["plan_key"]: p["role_id"] for p in plans if p["role_id"]}
                    self.recompensas = {
                        p["plan_key"]: {"coins": p["coins_reward"], "xp": p["xp_reward"]}
                        for p in plans
                    }
                    log.info("PixCog: catálogo premium carregado do DB (%d planos).", len(plans))
            except Exception as exc:
                log.warning("PixCog: falha ao carregar premium_catalog, usando defaults: %s", exc)
        from db.feature_config import validate_and_save_for_cog
        await validate_and_save_for_cog(self.bot, "premium", self)

    async def reload_feature_state(self) -> None:
        if self.bot.db is not None:
            cfg = getattr(self.bot, "config", None)
            guild_id = (cfg.get("guild_id") if cfg else None)
            if guild_id:
                from db.feature_config import is_feature_enabled
                self.feature_enabled = await is_feature_enabled(self.bot.db, guild_id, "premium")
        from db.feature_config import validate_and_save_for_cog
        await validate_and_save_for_cog(self.bot, "premium", self)

    async def validate_feature_config(self) -> list:
        from db.validators import validate_premium
        cfg = getattr(self.bot, "config", None)
        return validate_premium(cfg.to_dict() if cfg else {})

    # ─── grant premium via webhook (chamado pelo bot após NOTIFY) ─────────────

    async def grant_premium_rewards(self, user_id: int, plano: str) -> None:
        """Concede role, coins e XP quando premium é ativado via webhook do MP."""
        guild = self.bot.get_guild(self.bot.config.guild_id if self.bot.config else 0)
        if guild:
            member = guild.get_member(user_id)
            cargo_id = self.cargos.get(plano)
            if member and cargo_id:
                cargo = guild.get_role(cargo_id)
                if cargo and cargo not in member.roles:
                    try:
                        await member.add_roles(cargo)
                    except Exception as exc:
                        log.warning("Falha ao adicionar cargo %s para %s: %s", cargo_id, user_id, exc)

        recompensa = self.recompensas.get(plano, {})
        if recompensa.get("coins"):
            await self.adicionar_coins_manual(user_id, recompensa["coins"])
        if recompensa.get("xp"):
            await self.adicionar_xp_manual(user_id, recompensa["xp"])

        canal_log = self.bot.get_channel(
            self.bot.config.get("xp_log_channel_id") if self.bot.config else None
        )
        if canal_log:
            user = self.bot.get_user(user_id)
            embed = discord.Embed(
                title="💎 Plano Premium Ativado (Webhook)",
                description=(
                    f"**Usuário:** {user.mention if user else user_id}\n"
                    f"**Plano:** {plano.title()}\n"
                    f"**Recompensas:** {recompensa.get('coins', 0)} coins + {recompensa.get('xp', 0)} XP"
                ),
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow(),
            )
            if user:
                embed.set_thumbnail(url=user.display_avatar.url)
            await canal_log.send(embed=embed)

    async def carregar_emojis(self, guild):
        self.emoji_aventureiro = discord.utils.get(guild.emojis, name="aventureiro_premium")
        self.emoji_lendario = discord.utils.get(guild.emojis, name="lendario_premium")
        self.emoji_mitico = discord.utils.get(guild.emojis, name="mitico_premium")
        self.emoji_controle = discord.utils.get(guild.emojis, name="presente_fenrir")
        self.emoji_selecao = discord.utils.get(guild.emojis, name="inimigo_pirata")
        self.emoji_money_bag = discord.utils.get(guild.emojis, name="money_bag")
        self.emoji_presentinho = discord.utils.get(guild.emojis, name="presentinho")
        self.emoji_pix = discord.utils.get(guild.emojis, name="Pix")
        self.emoji_verify = discord.utils.get(guild.emojis, name="verify")
        self.emoji_voltar = discord.utils.get(guild.emojis, name="SA_RedLeftPoint")
        self.emoji_timer = discord.utils.get(guild.emojis, name="Timer")
        
        if not self.emoji_aventureiro:
            self.emoji_aventureiro = "🟤"
        if not self.emoji_lendario:
            self.emoji_lendario = "🔴"
        if not self.emoji_mitico:
            self.emoji_mitico = "🟡"
        if not self.emoji_controle:
            self.emoji_controle = "🎮"
        if not self.emoji_selecao:
            self.emoji_selecao = "⚔️"
        if not self.emoji_money_bag:
            self.emoji_money_bag = "💰"
        if not self.emoji_presentinho:
            self.emoji_presentinho = "🎁"
        if not self.emoji_pix:
            self.emoji_pix = "📱"
        if not self.emoji_verify:
            self.emoji_verify = "✅"
        if not self.emoji_voltar:
            self.emoji_voltar = "↩️"
        if not self.emoji_timer:
            self.emoji_timer = "⏰"

    async def setup_planos_embed(self, canal: discord.TextChannel):
        try:
            await self.carregar_emojis(canal.guild)
            
            if not canal:
                print("❌ Canal não encontrado.")
                return

            deleted_count = 0
            async for message in canal.history(limit=10):
                if message.author == self.bot.user:
                    await message.delete()
                    deleted_count += 1
                    await asyncio.sleep(0.5)

            embed = discord.Embed(
                title=f"{self.emoji_controle} Premium - Alcateia do Fenrir",
                description="> Escolha o plano que melhor se\n > adequa às suas necessidades:",
                color=discord.Color.dark_gold()
            )
            embed.set_thumbnail(
                url="https://cdn.discordapp.com/attachments/1427404744179060796/1430902885717381171/Lobo_a_Oferecer_Presente.png?ex=68fb77a8&is=68fa2628&hm=6965fbd9f309610b5f7437db24b13a788abfee037f408717f91382f5ef4206df&"
            )
            embed.set_image(
                url="https://cdn.discordapp.com/attachments/402510879918391297/1431078439762395176/Aventureiro.png?ex=68fc1b28&is=68fac9a8&hm=cfe10b0cb4c8e22d2b8f5232dd498ce6667268837f61f7e4f481df56161586e2&"
            )
            embed.set_footer(text="Selecione um plano abaixo para iniciar o pagamento")

            view = PlanosSelectView(
                self.emoji_selecao,
                self.emoji_aventureiro,
                self.emoji_lendario,
                self.emoji_mitico
            )
            
            await canal.send(embed=embed, view=view)


        except Exception as e:
            print(f"❌ Erro no setup_planos_embed: {e}")

    async def criar_canal_pagamento(self, interaction: discord.Interaction, plano: str):
        guild = interaction.guild
        categoria = guild.get_channel(1430229807450558504)
        
        if not categoria:
            await interaction.response.send_message("❌ Categoria não encontrada.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        canal = await categoria.create_text_channel(
            name=f"pagamento-{interaction.user.name}-{plano}",
            overwrites=overwrites
        )

        await interaction.response.send_message(
            f"📋 Canal de pagamento criado: {canal.mention}",
            ephemeral=True
        )

        await self.gerar_pix_no_canal(canal, interaction.user, plano)

    async def gerar_pix_no_canal(self, canal, usuario, plano):
        valor = self.planos[plano]

        payment_data = {
            "transaction_amount": float(valor),
            "description": f"Plano Premium {plano.capitalize()}",
            "payment_method_id": "pix",
            "payer": {
                "email": f"{usuario.id}@discord.com",
                "first_name": usuario.name,
                "last_name": "Usuario"
            },
            "external_reference": f"premium_{plano}_{usuario.id}",
        }

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self.mp_sdk.payment().create, payment_data),
                timeout=30.0
            )
            
            payment = result["response"]
            
            if result.get("status", 200) >= 400:
                embed = discord.Embed(
                    title="❌ Erro no Pagamento",
                    description=f"Erro: {payment.get('message', 'Erro desconhecido')}",
                    color=0xff0000
                )
                await canal.send(embed=embed)
                return
            
            if "point_of_interaction" not in payment:
                embed = discord.Embed(
                    title="❌ Erro ao Gerar PIX",
                    description="Não foi possível gerar o QR Code PIX.",
                    color=0xff0000
                )
                await canal.send(embed=embed)
                return

            transaction_data = payment["point_of_interaction"]["transaction_data"]
            qr_base64 = transaction_data["qr_code_base64"]
            qr_text = transaction_data["qr_code"]
            qr_bytes = BytesIO(base64.b64decode(qr_base64))
            file = discord.File(qr_bytes, filename="pix.png")

            recompensa = self.recompensas[plano]
            
            embed = discord.Embed(
                title=f"{self.emoji_money_bag} Pagamento - Plano {plano.capitalize()}",
                description=f"**Valor:** R$ {valor:.2f}\n**Plano:** {plano.capitalize()}",
                color=0x00ff00
            )
            
            embed.add_field(
                name=f"{self.emoji_presentinho} Recompensas",
                value=f"• {recompensa['coins']} coins\n• {recompensa['xp']} XP\n• Cargo exclusivo",
                inline=False
            )
            
            embed.add_field(
                name=f"{self.emoji_timer} Prazo",
                value="O pagamento deve ser efetuado em até **30 minutos**",
                inline=False
            )
            
            embed.add_field(
                name=f"{self.emoji_pix} Código PIX",
                value=f"```{qr_text}```",
                inline=False
            )
            
            embed.add_field(
                name=f"{self.emoji_verify} Após o Pagamento",
                value=f"Você receberá o cargo <@&{self.cargos[plano]}> automaticamente",
                inline=False
            )

            embed.set_footer(text="Clique em 'Voltar' para cancelar e fechar este canal")

            view = PagamentoView(self, plano, usuario.id, self.cargos[plano], self.emoji_verify, self.emoji_voltar)
            view.message = await canal.send(embed=embed, file=file, view=view)

        except Exception as e:
            embed = discord.Embed(
                title="❌ Erro no Processamento",
                description=f"Erro: {str(e)}",
                color=0xff0000
            )
            await canal.send(embed=embed)

    async def confirmar_pagamento(self, user_id, cargo_id, canal):
        try:
            guild = canal.guild
            member = guild.get_member(user_id)
            cargo = guild.get_role(cargo_id)

            if not member or not cargo:
                embed = discord.Embed(
                    title="❌ Erro",
                    description="Membro ou cargo não encontrado.",
                    color=0xff0000
                )
                await canal.send(embed=embed)
                return

            await member.add_roles(cargo)

            plano = None
            for plan_name, plan_cargo_id in self.cargos.items():
                if plan_cargo_id == cargo_id:
                    plano = plan_name
                    break
            
            if not plano:
                embed = discord.Embed(
                    title="❌ Erro",
                    description="Plano não encontrado.",
                    color=0xff0000
                )
                await canal.send(embed=embed)
                return

            await self.atualizar_premium_usuario(user_id, plano)

            recompensa = self.recompensas[plano]

            await self.adicionar_coins_manual(user_id, recompensa["coins"])

            await self.adicionar_xp_manual(user_id, recompensa["xp"])
            
            embed = discord.Embed(
                title=f"{self.emoji_verify} Pagamento Confirmado!",
                description=(
                    f"O cargo {cargo.mention} foi adicionado com sucesso!\n"
                    f"**Recompensas recebidas:**\n"
                    f"• {recompensa['coins']} coins\n"
                    f"• {recompensa['xp']} XP\n"
                    f"• Multiplicador de XP/coins ativado!"
                ),
                color=0x00ff00
            )
            await canal.send(embed=embed)

            canal_log = self.bot.get_channel(self.bot.config.get("xp_log_channel_id") if self.bot.config else None)
            if canal_log:
                embed_log = discord.Embed(
                    title="💎 Plano Premium Ativado",
                    description=(
                        f"**Usuário:** {member.mention}\n"
                        f"**Plano:** {plano.title()}\n"
                        f"**Recompensas:** {recompensa['coins']} coins + {recompensa['xp']} XP\n"
                        f"**Cargo:** {cargo.mention}"
                    ),
                    color=discord.Color.gold(),
                    timestamp=discord.utils.utcnow()
                )
                embed_log.set_thumbnail(url=member.display_avatar.url)
                await canal_log.send(embed=embed_log)
            
            await asyncio.sleep(10)
            await canal.delete()
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Erro ao Confirmar Pagamento",
                description=f"Erro: {str(e)}",
                color=0xff0000
            )
            await canal.send(embed=embed)
            print(f"Erro ao confirmar pagamento: {e}")

    async def atualizar_premium_usuario(self, user_id: int, plano: str):
        if self.use_db:
            try:
                expira = datetime.now(timezone.utc) + timedelta(days=30)
                await users_repo.set_premium(self.bot.db, user_id, plano, expira)
                uid_str = str(user_id)
                for cog_name in ("FenrirCoins", "XPCog"):
                    cog = self.bot.get_cog(cog_name)
                    if cog and uid_str in getattr(cog, "user_data", {}):
                        cog.user_data[uid_str]["premium"] = plano
                return
            except Exception as e:
                log.error("Erro ao atualizar premium (DB) para %s: %s", user_id, e)
                # Não faz fallback — erro de DB é crítico aqui

        # ── Fallback JSON ──────────────────────────────────────────────────────
        try:
            with open("data/user_data.json", "r", encoding="utf-8") as f:
                user_data = json.load(f)

            user_id_str = str(user_id)
            if user_id_str not in user_data:
                user_data[user_id_str] = {
                    "xp": 0, "nivel": 1, "titulo": "Aprendiz", "dobro": False,
                    "premium": None, "coins": 0, "daily_streak": 0,
                    "last_daily": None, "total_ganho": 0, "premium_expiracao": None,
                }

            expiracao = datetime.now().timestamp() + (30 * 24 * 60 * 60)
            user_data[user_id_str]["premium"] = plano
            user_data[user_id_str]["premium_expiracao"] = expiracao

            with open("data/user_data.json", "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=4, ensure_ascii=False)

        except Exception as e:
            print(f"❌ Erro ao atualizar premium do usuário {user_id}: {e}")
            
    @tasks.loop(hours=1)
    async def verificar_premium_loop(self):
        try:
            await self._executar_verificacao_premium()
        except Exception as e:
            print(f"❌ Erro na verificação de premium: {e}")

    @verificar_premium_loop.before_loop
    async def antes_de_verificar_premium(self):
        await self.bot.wait_until_ready()

    async def _executar_verificacao_premium(self):
        if self.use_db:
            await self._verificar_premium_db()
        else:
            await self._verificar_premium_json()

    async def _verificar_premium_db(self):
        """Remove premiums expirados diretamente do banco."""
        try:
            agora = datetime.now(timezone.utc)
            async with self.bot.db.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT user_id, premium FROM users
                    WHERE premium IS NOT NULL
                      AND premium_expira IS NOT NULL
                      AND premium_expira < $1
                    """,
                    agora,
                )
                if not rows:
                    return

                user_ids = [r["user_id"] for r in rows]
                await conn.execute(
                    """
                    UPDATE users
                    SET premium = NULL, premium_expira = NULL, updated_at = NOW()
                    WHERE user_id = ANY($1::bigint[])
                    """,
                    user_ids,
                )

            usuarios_removidos = [(str(r["user_id"]), r["premium"]) for r in rows]
            guild = self.bot.get_guild(self.bot.config.guild_id if self.bot.config else 0)

            for uid_str, _plano in usuarios_removidos:
                # Invalida caches em memória
                for cog_name in ("FenrirCoins", "XPCog"):
                    cog = self.bot.get_cog(cog_name)
                    if cog and uid_str in getattr(cog, "user_data", {}):
                        cog.user_data[uid_str]["premium"] = None

                # Remove cargo no Discord
                if guild:
                    member = guild.get_member(int(uid_str))
                    if member:
                        for cargo_id in self.cargos.values():
                            cargo = guild.get_role(cargo_id)
                            if cargo and cargo in member.roles:
                                try:
                                    await member.remove_roles(cargo)
                                except Exception as e:
                                    print(f"⚠️ Erro ao remover cargo do usuário {uid_str}: {e}")

            await self._enviar_log_expirados(usuarios_removidos)

        except Exception as e:
            print(f"❌ Erro ao verificar premium (DB): {e}")
            raise

    async def _verificar_premium_json(self):
        """Remove premiums expirados do JSON legado."""
        try:
            with open("data/user_data.json", "r", encoding="utf-8") as f:
                user_data = json.load(f)

            agora = datetime.now().timestamp()
            atualizado = False
            usuarios_removidos = []

            for user_id_str, data in user_data.items():
                if data.get("premium") and data.get("premium_expiracao"):
                    if data["premium_expiracao"] < agora:
                        plano_expirado = data["premium"]
                        data["premium"] = None
                        data["premium_expiracao"] = None
                        atualizado = True
                        usuarios_removidos.append((user_id_str, plano_expirado))

                        try:
                            guild = self.bot.get_guild(self.bot.config.guild_id if self.bot.config else 0)
                            if guild:
                                member = guild.get_member(int(user_id_str))
                                if member:
                                    for cargo_id in self.cargos.values():
                                        cargo = guild.get_role(cargo_id)
                                        if cargo and cargo in member.roles:
                                            await member.remove_roles(cargo)
                        except Exception as e:
                            print(f"⚠️ Erro ao remover cargo do usuário {user_id_str}: {e}")

            if atualizado:
                with open("data/user_data.json", "w", encoding="utf-8") as f:
                    json.dump(user_data, f, indent=4, ensure_ascii=False)

            await self._enviar_log_expirados(usuarios_removidos)

        except Exception as e:
            print(f"❌ Erro ao executar verificação de premium: {e}")
            raise

    async def _enviar_log_expirados(self, usuarios_removidos: list):
        """Envia embed de log com premiums expirados."""
        if not usuarios_removidos:
            return
        canal_log = self.bot.get_channel(
            self.bot.config.get("xp_log_channel_id") if self.bot.config else None
        )
        if not canal_log:
            return

        embed = discord.Embed(
            title="⏰ Premiums Expirados Removidos",
            description=f"**Total de usuários:** {len(usuarios_removidos)}",
            color=0xFF9900,
            timestamp=discord.utils.utcnow(),
        )
        for uid_str, plano in usuarios_removidos[:10]:
            user = self.bot.get_user(int(uid_str))
            nome_user = user.mention if user else f"ID: {uid_str}"
            embed.add_field(name=nome_user, value=f"Plano: {plano.title()}", inline=True)

        if len(usuarios_removidos) > 10:
            embed.add_field(
                name="...",
                value=f"E mais {len(usuarios_removidos) - 10} usuários",
                inline=False,
            )

        await canal_log.send(embed=embed)

    def cog_unload(self):
        self.verificar_premium_loop.cancel()

    async def adicionar_coins_manual(self, user_id, quantidade):
        # Tenta rotear pelo cog de coins (já tem suporte DB + cache + logs)
        coins_cog = self.bot.get_cog("FenrirCoins")
        if coins_cog:
            try:
                await coins_cog.adicionar_coins_sem_multiplo(
                    user_id, quantidade, "Compra de plano premium"
                )
                return
            except Exception as e:
                log.warning("FenrirCoins.adicionar_coins_sem_multiplo falhou: %s", e)

        # ── Fallback JSON ──────────────────────────────────────────────────────
        try:
            with open("data/user_data.json", "r", encoding="utf-8") as f:
                user_data = json.load(f)

            user_id_str = str(user_id)
            if user_id_str not in user_data:
                user_data[user_id_str] = {
                    "xp": 0, "nivel": 1, "titulo": "Aprendiz", "dobro": False,
                    "premium": None, "coins": 0, "daily_streak": 0,
                    "last_daily": None, "total_ganho": 0,
                }

            user_data[user_id_str]["coins"]      += quantidade
            user_data[user_id_str]["total_ganho"] += quantidade

            with open("data/user_data.json", "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=4, ensure_ascii=False)

            canal_log = self.bot.get_channel(
                self.bot.config.get("coins_log_channel_id") if self.bot.config else None
            )
            if canal_log:
                user = self.bot.get_user(user_id)
                if user:
                    embed = discord.Embed(
                        title="💰 Coins Adicionadas (Premium)",
                        description=(
                            f"**Usuário:** {user.mention} (`{user_id}`)\n"
                            f"**Valor:** +{quantidade} coins\n"
                            f"**Motivo:** Compra de plano premium\n"
                            f"**Data:** {discord.utils.format_dt(discord.utils.utcnow(), 'F')}"
                        ),
                        color=discord.Color.green(),
                    )
                    await canal_log.send(embed=embed)

        except Exception as e:
            print(f"❌ Erro ao adicionar coins manualmente: {e}")

    async def adicionar_xp_manual(self, user_id, xp_ganho):
        # Tenta rotear pelo cog de XP (já tem suporte DB + cache + logs)
        xp_cog = self.bot.get_cog("XPCog")
        if xp_cog:
            try:
                await xp_cog.adicionar_xp_sem_multiplo(user_id, xp_ganho, "Compra de plano premium")
                return
            except Exception as e:
                log.warning("XPCog.adicionar_xp_sem_multiplo falhou: %s", e)

        # ── Fallback JSON ──────────────────────────────────────────────────────
        try:
            with open("data/user_data.json", "r", encoding="utf-8") as f:
                user_data = json.load(f)

            user_id_str = str(user_id)
            if user_id_str not in user_data:
                user_data[user_id_str] = {
                    "xp": 0, "nivel": 1, "titulo": "Aprendiz", "dobro": False,
                    "premium": None, "coins": 0, "daily_streak": 0,
                    "last_daily": None, "total_ganho": 0,
                }

            user_data[user_id_str]["xp"] += xp_ganho

            with open("data/user_data.json", "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=4, ensure_ascii=False)

            canal_log = self.bot.get_channel(
                self.bot.config.get("xp_log_channel_id") if self.bot.config else None
            )
            if canal_log:
                user = self.bot.get_user(user_id)
                if user:
                    embed = discord.Embed(
                        title="⭐ XP Adicionado (Premium)",
                        description=(
                            f"**Usuário:** {user.mention} (`{user_id}`)\n"
                            f"**Valor:** +{xp_ganho} XP\n"
                            f"**Motivo:** Compra de plano premium\n"
                            f"**Data:** {discord.utils.format_dt(discord.utils.utcnow(), 'F')}"
                        ),
                        color=discord.Color.blue(),
                    )
                    await canal_log.send(embed=embed)

        except Exception as e:
            print(f"❌ Erro ao adicionar XP manualmente: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(5)

class PlanosSelectView(discord.ui.View):
    def __init__(self, emoji_selecao, emoji_aventureiro, emoji_lendario, emoji_mitico):
        super().__init__(timeout=None)
        self.emoji_selecao = emoji_selecao
        self.emoji_aventureiro = emoji_aventureiro
        self.emoji_lendario = emoji_lendario
        self.emoji_mitico = emoji_mitico
        
        self.select = discord.ui.Select(
            placeholder="Selecione seu plano...",   
            options=[
                discord.SelectOption(label="Aventureiro", value="aventureiro", emoji=self.emoji_aventureiro),
                discord.SelectOption(label="Lendário", value="lendario", emoji=self.emoji_lendario),
                discord.SelectOption(label="Mítico", value="mitico", emoji=self.emoji_mitico)
            ]
        )
        self.select.callback = self.select_plano
        self.add_item(self.select)

    async def select_plano(self, interaction: discord.Interaction):
        plano = self.select.values[0]
        cog = interaction.client.get_cog("PixCog")
        await cog.criar_canal_pagamento(interaction, plano)

class PagamentoView(discord.ui.View):
    def __init__(self, pix_cog, plano, user_id, cargo_id, emoji_verify, emoji_voltar):
        super().__init__(timeout=1800)
        self.pix_cog = pix_cog
        self.plano = plano
        self.user_id = user_id
        self.cargo_id = cargo_id
        self.emoji_verify = emoji_verify
        self.emoji_voltar = emoji_voltar

        self.confirmar_button = discord.ui.Button(
            label="Confirmar Pagamento", 
            style=discord.ButtonStyle.green,
            emoji=self.emoji_verify
        )
        self.confirmar_button.callback = self.confirmar
        
        self.voltar_button = discord.ui.Button(
            label="Voltar", 
            style=discord.ButtonStyle.gray,
            emoji=self.emoji_voltar
        )
        self.voltar_button.callback = self.voltar
        
        self.add_item(self.confirmar_button)
        self.add_item(self.voltar_button)

    async def confirmar(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            await self.pix_cog.confirmar_pagamento(self.user_id, self.cargo_id, interaction.channel)
            self.stop()
        except Exception as e:
            print(f"Erro no botão confirmar: {e}")
            await interaction.followup.send("❌ Erro ao confirmar pagamento.", ephemeral=True)

    async def voltar(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            title="❌ Pagamento Cancelado",
            description="O canal será fechado em 5 segundos.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)
        await asyncio.sleep(5)
        await interaction.channel.delete()
        self.stop()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        
        try:
            channel = self.message.channel
            embed = discord.Embed(
                title="⏰ Tempo Esgotado",
                description="O tempo para pagamento expirou. O canal será fechado.",
                color=0xff9900
            )
            await self.message.edit(view=self)
            await asyncio.sleep(5)
            await channel.delete()
        except Exception as e:
            print(f"Erro no timeout: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(PixCog(bot))