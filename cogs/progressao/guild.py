import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import time
from typing import Optional

import repositories.guilds as guilds_repo

log = logging.getLogger(__name__)


class GuildSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.use_db: bool = False
        self.feature_enabled: bool = True
        self.ARQUIVO_GUILDS = "data/guilds_data.json"

        self.xp_base = 500000
        self.recompensas_nivel = {
            1: {"banco": 0, "vantagens": "Guild básica"},
            2: {"banco": 10000, "vantagens": "+1 slot de admin"},
            3: {"banco": 25000, "vantagens": "Multiplicador +0.1x"},
            4: {"banco": 50000, "vantagens": "+5 slots de membros"},
            5: {"banco": 100000, "vantagens": "Multiplicador +0.2x"},
            6: {"banco": 200000, "vantagens": "+10 slots de membros"},
            7: {"banco": 350000, "vantagens": "Multiplicador +0.3x"},
            8: {"banco": 500000, "vantagens": "+15 slots de membros"},
            9: {"banco": 750000, "vantagens": "Multiplicador +0.5x"},
            10: {"banco": 1000000, "vantagens": "Título Lendário"},
            11: {"banco": 1500000, "vantagens": "Multiplicador +0.7x"},
            12: {"banco": 2000000, "vantagens": "+20 slots de membros"},
            13: {"banco": 3000000, "vantagens": "Multiplicador +1.0x"},
            14: {"banco": 4000000, "vantagens": "+25 slots de membros"},
            15: {"banco": 5000000, "vantagens": "Título Mítico"}
        }

        self.planos_config = {
            "gratuito": {
                "membros_max": 5,
                "admins_max": 1,
                "multiplicador_base": 1.0,
                "multiplicadores_membros": {5: 1.5},
                "xp_mult": 1.0,
                "farm_afk": False
            },
            "aventureiro": {
                "membros_max": 10,
                "admins_max": 2,
                "multiplicador_base": 1.0,
                "multiplicadores_membros": {5: 1.5, 10: 2.0},
                "xp_mult": 1.0,
                "farm_afk": False
            },
            "lendario": {
                "membros_max": 20,
                "admins_max": 3,
                "multiplicador_base": 1.0,
                "multiplicadores_membros": {5: 1.5, 10: 2.0, 20: 3.0},
                "xp_mult": 1.2,
                "farm_afk": False
            },
            "mitico": {
                "membros_max": 50,
                "admins_max": 5,
                "multiplicador_base": 1.0,
                "multiplicadores_membros": {5: 1.5, 10: 2.0, 20: 3.0, 50: 5.0},
                "xp_mult": 1.5,
                "farm_afk": True
            }
        }

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.feature_enabled:
            await interaction.response.send_message(
                "❌ O sistema de guildas não está habilitado neste servidor.", ephemeral=True
            )
            return False
        return True

    async def cog_load(self) -> None:
        self.use_db = self.bot.db is not None
        if self.bot.config:
            self.xp_base = self.bot.config.get("guild_xp_base") or self.xp_base
            db_rewards = self.bot.config.get("guild_level_rewards") or {}
            if db_rewards:
                self.recompensas_nivel = {int(k): v for k, v in db_rewards.items()}
        if self.use_db and not hasattr(self.bot, "_guilds_cache"):
            try:
                self.bot._guilds_cache = await guilds_repo.build_full_data(self.bot.db)
                n = len([k for k in self.bot._guilds_cache if k != "raids_ativas"])
                log.info("GuildSystem: %d guilds carregadas do DB", n)
            except Exception as exc:
                log.error("GuildSystem: erro ao carregar guilds do DB: %s", exc)
                self.bot._guilds_cache = {"raids_ativas": {}}
        from db.feature_config import load_feature_state_for_cog, validate_and_save_for_cog
        self.feature_enabled = await load_feature_state_for_cog(self.bot, "guilds")
        await validate_and_save_for_cog(self.bot, "guilds", self)

    async def validate_feature_config(self) -> list:
        from db.validators import validate_guilds
        cfg = getattr(self.bot, "config", None)
        return validate_guilds(cfg.to_dict() if cfg else {})

    async def reload_feature_state(self) -> None:
        from db.feature_config import load_feature_state_for_cog, validate_and_save_for_cog
        self.feature_enabled = await load_feature_state_for_cog(self.bot, "guilds")
        await validate_and_save_for_cog(self.bot, "guilds", self)

    def calcular_xp_necessario(self, nivel: int) -> int:
        return int(self.xp_base * (2 ** (nivel - 1)))

    def verificar_subida_nivel(self, guild_data: dict) -> tuple:
        nivel_atual = guild_data["nivel"]
        xp_atual = guild_data["xp"]
        xp_necessario = self.calcular_xp_necessario(nivel_atual)
        
        niveis_subidos = 0
        dados_atualizados = guild_data.copy()
        
        while xp_atual >= xp_necessario:
            nivel_atual += 1
            niveis_subidos += 1
            
            recompensa = self.recompensas_nivel.get(nivel_atual, {"banco": 0, "vantagens": "Nenhuma"})
            dados_atualizados["banco"] += recompensa["banco"]
            
            xp_necessario = self.calcular_xp_necessario(nivel_atual)
        
        if niveis_subidos > 0:
            dados_atualizados["nivel"] = nivel_atual
            return True, dados_atualizados, niveis_subidos
        
        return False, guild_data, 0

    def carregar_dados(self) -> dict:
        if self.use_db:
            cache = getattr(self.bot, "_guilds_cache", None)
            return cache if cache is not None else {"raids_ativas": {}}

        try:
            if os.path.exists(self.ARQUIVO_GUILDS):
                with open(self.ARQUIVO_GUILDS, "r", encoding="utf-8") as f:
                    dados = json.load(f)

                    if "raids_ativas" not in dados:
                        dados["raids_ativas"] = {}

                    for guild_id, guild_data in dados.items():
                        if guild_id == "raids_ativas":
                            continue
                        for field, default in [
                            ("membros", {}), ("banco", 0), ("nivel", 1), ("xp", 0),
                            ("motto", ""), ("emoji", ""), ("convites", {}), ("cooldowns", {}),
                            ("aliancas", []), ("data_criacao", time.time()),
                            ("ultima_raid", 0), ("data_alianca", 0),
                        ]:
                            if field not in guild_data:
                                guild_data[field] = default

                    return dados
        except Exception as e:
            print(f"❌ Erro ao carregar dados: {e}")

        return {"raids_ativas": {}}

    def salvar_dados(self, dados: dict) -> bool:
        if self.use_db:
            self.bot._guilds_cache = dados
            if self.bot.db is not None:
                asyncio.ensure_future(self._flush_to_db(dados))
            return True

        try:
            with open(self.ARQUIVO_GUILDS, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=4)
            return True
        except Exception as e:
            print(f"❌ Erro ao salvar dados: {e}")
            return False

    async def _flush_to_db(self, dados: dict) -> None:
        try:
            await guilds_repo.sync_full_data(self.bot.db, dados)
        except Exception as exc:
            log.error("GuildSystem: falha ao sincronizar guilds com DB: %s", exc)

    def obter_guild_por_membro(self, user_id: int) -> Optional[str]:
        dados = self.carregar_dados()
        user_id_str = str(user_id)
        
        for guild_id, guild_data in dados.items():
            if guild_id == "raids_ativas":
                continue
            if user_id_str in guild_data.get("membros", {}):
                return guild_id
        return None

    async def obter_plano_usuario(self, user_id: int) -> str:
        if self.use_db:
            # Prefer in-memory cache from FenrirCoins cog
            coins_cog = self.bot.get_cog("FenrirCoins")
            if coins_cog and str(user_id) in coins_cog.user_data:
                plano = coins_cog.user_data[str(user_id)].get("premium") or "gratuito"
                return plano if plano in self.planos_config else "gratuito"
            try:
                plano = await guilds_repo.get_premium_usuario(self.bot.db, user_id)
                return (plano or "gratuito") if (plano or "gratuito") in self.planos_config else "gratuito"
            except Exception as exc:
                log.error("Erro ao obter plano do usuário %s: %s", user_id, exc)
                return "gratuito"

        try:
            user_data_file = "data/user_data.json"
            if os.path.exists(user_data_file):
                with open(user_data_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                    plano = user_data.get(str(user_id), {}).get("premium", "gratuito")
                    return plano if plano in self.planos_config else "gratuito"
        except Exception as e:
            print(f"❌ Erro ao obter plano: {e}")
        return "gratuito"

    async def calcular_multiplicador_guild(self, guild_id: str) -> float:
        try:
            dados = self.carregar_dados()
            if guild_id not in dados or guild_id == "raids_ativas":
                return 1.0

            guild_data = dados[guild_id]
            plano_lider = await self.obter_plano_usuario(int(guild_data["lider"]))
            config_plano = self.planos_config.get(plano_lider, self.planos_config["gratuito"])
            
            membros_ativos = len([m for m in guild_data["membros"].values() if m.get("ativo", True)])
            
            multiplicador = config_plano["multiplicador_base"]
            
            for limite, mult in config_plano["multiplicadores_membros"].items():
                if membros_ativos >= limite and mult > multiplicador:
                    multiplicador = mult
            
            nivel_guild = guild_data.get("nivel", 1)
            if nivel_guild >= 3:
                multiplicador += 0.1
            if nivel_guild >= 5:
                multiplicador += 0.2
            if nivel_guild >= 7:
                multiplicador += 0.3
            if nivel_guild >= 9:
                multiplicador += 0.5
            if nivel_guild >= 11:
                multiplicador += 0.7
            if nivel_guild >= 13:
                multiplicador += 1.0
            
            return round(multiplicador, 1)
            
        except Exception as e:
            print(f"❌ Erro ao calcular multiplicador: {e}")
            return 1.0

    async def atualizar_guild_user_data(self, user_id: int, guild_id: str = None):
        if self.use_db:
            try:
                await guilds_repo.update_guild_name(self.bot.db, user_id, guild_id)
                # Atualiza cache em memória do FenrirCoins se disponível
                coins_cog = self.bot.get_cog("FenrirCoins")
                if coins_cog and str(user_id) in coins_cog.user_data:
                    coins_cog.user_data[str(user_id)]["guild"] = guild_id
            except Exception as exc:
                log.error("Erro ao atualizar guild_name do usuário %s: %s", user_id, exc)
            return

        try:
            user_data_file = "data/user_data.json"
            dados = {}

            if os.path.exists(user_data_file):
                with open(user_data_file, "r", encoding="utf-8") as f:
                    dados = json.load(f)

            user_id_str = str(user_id)
            if user_id_str not in dados:
                dados[user_id_str] = {}

            dados[user_id_str]["guild"] = guild_id

            with open(user_data_file, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=4)

        except Exception as e:
            print(f"❌ Erro ao atualizar user_data: {e}")

    def obter_coins_usuario(self, user_id: int) -> int:
        try:
            user_data_file = "data/user_data.json"
            if os.path.exists(user_data_file):
                with open(user_data_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                    return user_data.get(str(user_id), {}).get("coins", 0)
        except Exception as e:
            print(f"❌ Erro ao obter coins do usuário: {e}")
        return 0

    def atualizar_coins_usuario(self, user_id: int, coins: int):
        try:
            user_data_file = "data/user_data.json"
            dados = {}
            
            if os.path.exists(user_data_file):
                with open(user_data_file, "r", encoding="utf-8") as f:
                    dados = json.load(f)
            
            user_id_str = str(user_id)
            if user_id_str not in dados:
                dados[user_id_str] = {}
            
            dados[user_id_str]["coins"] = coins
            
            with open(user_data_file, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=4)
                
        except Exception as e:
            print(f"❌ Erro ao atualizar coins do usuário: {e}")

    @app_commands.command(name="guild_adicionar_xp", description="Adiciona XP à guild (apenas desenvolvedor)")
    @app_commands.describe(quantidade_xp="Quantidade de XP para adicionar", nome_guild="Nome da guild (opcional)")
    @app_commands.default_permissions(administrator=True)
    async def guild_add_xp(self, interaction: discord.Interaction, quantidade_xp: int, nome_guild: str = None):
        try:
            await interaction.response.defer(ephemeral=True)
            
            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ Você precisa ser administrador para usar este comando!")
                return
            
            if quantidade_xp <= 0:
                await interaction.followup.send("❌ A quantidade de XP deve ser maior que 0!")
                return
            
            dados = self.carregar_dados()
            guild_id_encontrada = None
            guild_nome_encontrada = None

            if not nome_guild:
                guild_id_encontrada = self.obter_guild_por_membro(interaction.user.id)
                if guild_id_encontrada and guild_id_encontrada in dados:
                    guild_nome_encontrada = dados[guild_id_encontrada]["nome"]
            else:
                for guild_id, guild_data in dados.items():
                    if guild_id == "raids_ativas":
                        continue
                    if guild_data.get("nome", "").lower() == nome_guild.lower():
                        guild_id_encontrada = guild_id
                        guild_nome_encontrada = guild_data["nome"]
                        break
            
            if not guild_id_encontrada:
                if nome_guild:
                    await interaction.followup.send(f"❌ Guild **{nome_guild}** não encontrada!")
                else:
                    await interaction.followup.send("❌ Você não está em uma guild e não forneceu um nome de guild!")
                return

            if guild_id_encontrada not in dados:
                await interaction.followup.send(f"❌ Guild {guild_id_encontrada} não encontrada!")
                return

            dados[guild_id_encontrada]["xp"] += quantidade_xp

            subiu_nivel, dados[guild_id_encontrada], niveis_subidos = self.verificar_subida_nivel(dados[guild_id_encontrada])

            if self.salvar_dados(dados):
                embed = discord.Embed(
                    title="🎯 XP Adicionado!",
                    color=discord.Color.green()
                )
                
                xp_atual = dados[guild_id_encontrada]["xp"]
                nivel_atual = dados[guild_id_encontrada]["nivel"]
                xp_necessario = self.calcular_xp_necessario(nivel_atual)
                
                if subiu_nivel:
                    embed.description = f"✅ **{quantidade_xp:,} XP** adicionado à guild **{guild_nome_encontrada}**! 🎉"
                    
                    recompensas_texto = ""
                    for i in range(niveis_subidos):
                        nivel_alcancado = nivel_atual - i
                        recompensa = self.recompensas_nivel.get(nivel_alcancado, {})
                        if recompensa.get("banco", 0) > 0:
                            recompensas_texto += f"**Nível {nivel_alcancado}**: +{recompensa['banco']:,}💰 | {recompensa['vantagens']}\n"
                    
                    if recompensas_texto:
                        embed.add_field(
                            name="🎁 Recompensas Conquistadas!",
                            value=recompensas_texto,
                            inline=False
                        )
                else:
                    embed.description = f"✅ **{quantidade_xp:,} XP** adicionado à guild **{guild_nome_encontrada}**!"
                
                embed.add_field(
                    name="🎯 Progresso Atual",
                    value=f"**Nível {nivel_atual}**\nXP: {xp_atual:,}/{xp_necessario:,}",
                    inline=True
                )
                embed.add_field(
                    name="💰 Banco",
                    value=f"**{dados[guild_id_encontrada]['banco']:,} coins**",
                    inline=True
                )

                progresso = min((xp_atual / xp_necessario) * 100, 100)
                barra = "█" * int(progresso / 10) + "░" * (10 - int(progresso / 10))
                embed.add_field(
                    name="📊 Progresso para Próximo Nível",
                    value=f"`{barra}` {progresso:.1f}%",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Erro ao salvar dados da guild!")
            
        except ValueError:
            await interaction.followup.send("❌ Por favor, forneça um número válido para o XP.")
        except Exception as e:
            print(f"❌ Erro em guild_add_xp: {e}")
            await interaction.followup.send(f"❌ Erro ao adicionar XP: {str(e)}")
            
    @app_commands.command(name="guild_progresso", description="Mostra a progressão de níveis da guild")
    async def guild_progress(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            
            guild_id = self.obter_guild_por_membro(interaction.user.id)
            if not guild_id:
                await interaction.followup.send("❌ Você não está em uma guild!")
                return
            
            dados = self.carregar_dados()
            guild_data = dados.get(guild_id)
            
            if not guild_data:
                await interaction.followup.send("❌ Guild não encontrada!")
                return
            
            nivel_atual = guild_data["nivel"]
            xp_atual = guild_data["xp"]
            xp_necessario = self.calcular_xp_necessario(nivel_atual)
            
            embed = discord.Embed(
                title=f"📊 Progressão de Níveis - {guild_data['nome']}",
                color=discord.Color.blue()
            )
            
            progresso = min((xp_atual / xp_necessario) * 100, 100)
            barra = "█" * int(progresso / 10) + "░" * (10 - int(progresso / 10))
            
            embed.add_field(
                name="🎯 Nível Atual",
                value=f"**Nível {nivel_atual}**\n"
                      f"XP: {xp_atual:,}/{xp_necessario:,}\n"
                      f"Progresso: `{barra}` {progresso:.1f}%",
                inline=False
            )
            
            proximos_niveis = ""
            for i in range(1, 4):
                nivel = nivel_atual + i
                if nivel <= 15:
                    xp_necessario_nivel = self.calcular_xp_necessario(nivel)
                    recompensa = self.recompensas_nivel.get(nivel, {"banco": 0, "vantagens": "Nenhuma"})
                    proximos_niveis += f"**Nível {nivel}**: {xp_necessario_nivel:,} XP | +{recompensa['banco']:,}💰 | {recompensa['vantagens']}\n"
            
            if proximos_niveis:
                embed.add_field(
                    name="📈 Próximos Níveis",
                    value=proximos_niveis,
                    inline=False
                )
     
            referencia = "```\nNível  XP Necessário    Recompensa Banco    Vantagens\n"
            referencia += "-----  --------------    -----------------    ----------\n"
            for nivel in [1, 2, 3, 5, 7, 10, 13, 15]:
                xp_needed = self.calcular_xp_necessario(nivel)
                recompensa = self.recompensas_nivel.get(nivel, {"banco": 0, "vantagens": "Nenhuma"})
                bonus = recompensa["banco"]
                vantagem = recompensa["vantagens"][:20] + "..." if len(recompensa["vantagens"]) > 20 else recompensa["vantagens"]
                
                referencia += f"{nivel:2d}     {xp_needed:12,}    {bonus:10,}💰    {vantagem}\n"
            referencia += "```"
            
            embed.add_field(
                name="📋 Tabela de Progressão",
                value=referencia,
                inline=False
            )
        
            multiplicador = await self.calcular_multiplicador_guild(guild_id)
            embed.add_field(
                name="⚡ Multiplicador Atual",
                value=f"**{multiplicador}x** (baseado no plano + bônus de nível)",
                inline=True
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"❌ Erro em guild_progress: {e}")
            await interaction.followup.send("❌ Erro ao mostrar progresso!")

    @app_commands.command(name="guild_listar", description="Lista todas as guilds com seus IDs")
    @app_commands.default_permissions(administrator=True)
    async def guild_list(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            dados = self.carregar_dados()
            guilds_validas = {k: v for k, v in dados.items() if k != "raids_ativas"}
            
            if not guilds_validas:
                await interaction.followup.send("❌ Nenhuma guild criada ainda!")
                return
            
            embed = discord.Embed(
                title="📋 Lista de Guilds",
                description="IDs de todas as guilds para uso administrativo:",
                color=discord.Color.blue()
            )
            
            for guild_id, guild_data in guilds_validas.items():
                embed.add_field(
                    name=f"🏰 {guild_data['nome']}",
                    value=f"**ID:** `{guild_id}`\n**Líder:** <@{guild_data['lider']}>\n**Nível:** {guild_data['nivel']} | **XP:** {guild_data['xp']:,}",
                    inline=False
                )
            
            embed.set_footer(text="Use /guild_adicionar_xp com estes IDs para adicionar XP")
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"❌ Erro em guild_list: {e}")
            await interaction.followup.send("❌ Erro ao listar guilds!")

    @app_commands.command(name="guild_criar", description="Cria uma nova guild")
    @app_commands.describe(nome="Nome da guild")
    async def guild_create(self, interaction: discord.Interaction, nome: str):
        try:
            await interaction.response.defer(ephemeral=True)
            
            user_id = str(interaction.user.id)
            dados = self.carregar_dados()
            
            if self.obter_guild_por_membro(interaction.user.id):
                await interaction.followup.send("❌ Você já está em uma guild!")
                return
            
            for guild_data in dados.values():
                if guild_data.get("nome", "").lower() == nome.lower():
                    await interaction.followup.send("❌ Já existe uma guild com este nome!")
                    return
            
            plano = await self.obter_plano_usuario(interaction.user.id)
            config_plano = self.planos_config.get(plano, self.planos_config["gratuito"])
            
            guild_id = f"guild_{int(time.time())}"
            dados[guild_id] = {
                "nome": nome,
                "lider": user_id,
                "membros": {
                    user_id: {
                        "cargo": "Líder",
                        "entrada": time.time(),
                        "ativo": True
                    }
                },
                "banco": 0,
                "nivel": 1,
                "xp": 0,
                "motto": "",
                "emoji": "",
                "convites": {},
                "cooldowns": {},
                "aliancas": [],
                "data_criacao": time.time(),
                "ultima_raid": 0,
                "data_alianca": 0
            }
            
            if self.salvar_dados(dados):
                await self.atualizar_guild_user_data(interaction.user.id, guild_id)
                
                embed = discord.Embed(
                    title="🏰 Guild Criada!",
                    description=f"**{nome}** foi criada com sucesso!",
                    color=discord.Color.green()
                )
                embed.add_field(name="👑 Líder", value=interaction.user.mention, inline=True)
                embed.add_field(name="💎 Plano", value=plano.title(), inline=True)
                embed.add_field(name="👥 Limite", value=config_plano["membros_max"], inline=True)
                embed.add_field(name="💰 Multiplicador Máximo", value=f"{self.calcular_multiplicador_guild(guild_id)}x", inline=True)
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Erro ao criar guild!")
            
        except Exception as e:
            print(f"❌ Erro em guild_create: {e}")
            await interaction.followup.send("❌ Erro ao criar guild!")

    @app_commands.command(name="guild_info", description="Mostra informações da guild")
    @app_commands.describe(nome="Nome da guild (opcional)")
    async def guild_info(self, interaction: discord.Interaction, nome: str = None):
        try:
            await interaction.response.defer()
            
            dados = self.carregar_dados()
            guild_data = None
            guild_id = None
            
            if nome:
                for gid, gdata in dados.items():
                    if gid != "raids_ativas" and gdata.get("nome", "").lower() == nome.lower():
                        guild_data = gdata
                        guild_id = gid
                        break
            else:
                guild_id = self.obter_guild_por_membro(interaction.user.id)
                if guild_id and guild_id in dados:
                    guild_data = dados[guild_id]
            
            if not guild_data:
                await interaction.followup.send("❌ Guild não encontrada!")
                return
            
            plano_lider = await self.obter_plano_usuario(int(guild_data["lider"]))
            multiplicador = await self.calcular_multiplicador_guild(guild_id)
            
            embed = discord.Embed(
                title=f"🏰 {guild_data['nome']}",
                color=discord.Color.gold()
            )
            
            if guild_data.get("motto"):
                embed.description = f"*{guild_data['motto']}*"
            
            embed.add_field(name="👑 Líder", value=f"<@{guild_data['lider']}>", inline=True)
            embed.add_field(name="💎 Plano", value=plano_lider.title(), inline=True)
            embed.add_field(name="📊 Nível", value=f"Level {guild_data['nivel']}", inline=True)
            embed.add_field(name="👥 Membros", value=f"{len(guild_data['membros'])}", inline=True)
            embed.add_field(name="💰 Banco", value=f"{guild_data['banco']:,} coins", inline=True)
            embed.add_field(name="⚡ Multiplicador", value=f"{multiplicador}x", inline=True)
            
            if guild_data.get("emoji"):
                embed.add_field(name="🎨 Emoji", value=guild_data["emoji"], inline=True)
            
            xp_proximo = self.calcular_xp_necessario(guild_data["nivel"])
            progresso = min(guild_data["xp"] / xp_proximo * 100, 100) if xp_proximo > 0 else 0
            embed.add_field(name="🎯 Progresso", value=f"{guild_data['xp']:,}/{xp_proximo:,} XP ({progresso:.1f}%)", inline=False)
            
            aliancas = guild_data.get("aliancas", [])
            if aliancas:
                aliados_str = ""
                for aliado_id in aliancas[:3]:
                    if aliado_id in dados:
                        aliado_data = dados[aliado_id]
                        aliados_str += f"• {aliado_data['nome']}\n"
                if len(aliancas) > 3:
                    aliados_str += f"• e mais {len(aliancas) - 3}...\n"
                embed.add_field(name="🤝 Alianças", value=aliados_str or "Nenhuma", inline=True)
            
            dias_criacao = int((time.time() - guild_data["data_criacao"]) / 86400)
            embed.set_image(url="https://cdn.discordapp.com/attachments/1288876556898275328/1431257799286849597/2sre110i6u8c1.gif?ex=68fcc232&is=68fb70b2&hm=5947224d45562874accaea43fa48c2726826563a0e63ed077c8c2fa39fe2adc6&")
            embed.set_footer(text=f"Criada há {dias_criacao} dias")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"❌ Erro em guild_info: {e}")
            await interaction.followup.send("❌ Erro ao buscar informações da guild!")

    @app_commands.command(name="guild_membros", description="Lista todos os membros da guild")
    async def guild_members(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            
            guild_id = self.obter_guild_por_membro(interaction.user.id)
            if not guild_id:
                await interaction.followup.send("❌ Você não está em uma guild!")
                return
            
            dados = self.carregar_dados()
            guild_data = dados.get(guild_id)
            
            if not guild_data:
                await interaction.followup.send("❌ Guild não encontrada!")
                return
            
            embed = discord.Embed(
                title=f"👥 Membros de {guild_data['nome']}",
                color=discord.Color.blue()
            )
            
            membros_ordenados = sorted(
                guild_data["membros"].items(),
                key=lambda x: (["Líder", "Admin", "Membro"].index(x[1]["cargo"]), x[1]["entrada"])
            )
            
            for user_id, membro_data in membros_ordenados:
                user = self.bot.get_user(int(user_id))
                nome = user.display_name if user else f"Usuário {user_id}"
                cargo = membro_data["cargo"]
                dias = int((time.time() - membro_data["entrada"]) / 86400)
                
                embed.add_field(
                    name=f"{cargo} - {nome}",
                    value=f"Entrou há {dias} dias",
                    inline=False
                )
            
            embed.set_footer(text=f"Total: {len(guild_data['membros'])} membros")
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"❌ Erro em guild_members: {e}")
            await interaction.followup.send("❌ Erro ao listar membros!")

    @app_commands.command(name="guild_sair", description="Sai da guild atual")
    async def guild_leave(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            guild_id = self.obter_guild_por_membro(interaction.user.id)
            if not guild_id:
                await interaction.followup.send("❌ Você não está em uma guild!")
                return
            
            dados = self.carregar_dados()
            guild_data = dados.get(guild_id)
            
            if not guild_data:
                await interaction.followup.send("❌ Guild não encontrada!")
                return
            
            user_id = str(interaction.user.id)
            
            if guild_data["lider"] == user_id:
                await interaction.followup.send("❌ Líderes não podem sair da guild! Use `/guild_transfer` ou `/guild_deletar`")
                return
            
            if user_id in guild_data["membros"]:
                del guild_data["membros"][user_id]
                dados[guild_id] = guild_data
                
                if self.salvar_dados(dados):
                    await self.atualizar_guild_user_data(interaction.user.id, None)
                    await interaction.followup.send(f"✅ Você saiu da guild **{guild_data['nome']}**")
                else:
                    await interaction.followup.send("❌ Erro ao salvar dados!")
            else:
                await interaction.followup.send("❌ Membro não encontrado na guild!")
            
        except Exception as e:
            print(f"❌ Erro em guild_leave: {e}")
            await interaction.followup.send("❌ Erro ao sair da guild!")

    @app_commands.command(name="guild_ranking", description="Mostra o ranking das guilds")
    async def guild_ranking(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=False)
            
            dados = self.carregar_dados()
            guilds_validas = {k: v for k, v in dados.items() if k != "raids_ativas"}
            
            if not guilds_validas:
                await interaction.followup.send("❌ Nenhuma guild criada ainda!")
                return
            
            guilds_ordenadas = sorted(
                guilds_validas.items(),
                key=lambda x: (x[1]["nivel"], x[1]["xp"]),
                reverse=True
            )[:10]
            
            embed = discord.Embed(
                title="🏆 Ranking de Guilds",
                color=discord.Color.gold()
            )
            
            for i, (guild_id, guild_data) in enumerate(guilds_ordenadas, 1):
                plano_lider = await self.obter_plano_usuario(int(guild_data["lider"]))
                multiplicador = await self.calcular_multiplicador_guild(guild_id)
                
                embed.add_field(
                    name=f"{i}. {guild_data['nome']}",
                    value=f"Level: {guild_data['nivel']} | XP: {guild_data['xp']:,}\nMembros: {len(guild_data['membros'])} | Banco: {guild_data['banco']:,} coins\nPlano: {plano_lider.title()} | Multi: {multiplicador}x",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"❌ Erro em guild_ranking: {e}")
            try:
                await interaction.followup.send("❌ Erro ao carregar ranking!", ephemeral=True)
            except:
                pass

    @app_commands.command(name="guild_convidar", description="Convida um usuário para a guild")
    @app_commands.describe(usuario="Usuário para convidar")
    async def guild_invite(self, interaction: discord.Interaction, usuario: discord.Member):
        try:
            await interaction.response.defer(ephemeral=True)
            
            guild_id = self.obter_guild_por_membro(interaction.user.id)
            if not guild_id:
                await interaction.followup.send("❌ Você não está em uma guild!")
                return
            
            dados = self.carregar_dados()
            guild_data = dados.get(guild_id)
            
            if not guild_data:
                await interaction.followup.send("❌ Guild não encontrada!")
                return
            
            user_cargo = guild_data["membros"].get(str(interaction.user.id), {}).get("cargo")
            if user_cargo not in ["Líder", "Admin"]:
                await interaction.followup.send("❌ Apenas líderes e administradores podem convidar membros!")
                return
            
            if self.obter_guild_por_membro(usuario.id):
                await interaction.followup.send(f"❌ {usuario.mention} já está em uma guild!")
                return
            
            plano = self.obter_plano_usuario(int(guild_data["lider"]))
            config_plano = self.planos_config.get(plano, self.planos_config["gratuito"])
            
            if len(guild_data["membros"]) >= config_plano["membros_max"]:
                await interaction.followup.send(f"❌ Limite de {config_plano['membros_max']} membros atingido!")
                return
            
            convite_id = f"convite_{int(time.time())}"
            if "convites" not in guild_data:
                guild_data["convites"] = {}
                
            guild_data["convites"][convite_id] = {
                "usuario": str(usuario.id),
                "criador": str(interaction.user.id),
                "data": time.time(),
                "expiracao": time.time() + 86400
            }
            
            dados[guild_id] = guild_data
            
            if self.salvar_dados(dados):
                embed = discord.Embed(
                    title="📨 Convite Enviado!",
                    description=f"Convite enviado para {usuario.mention}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="⏰ Válido por", value="24 horas", inline=True)
                embed.add_field(name="👥 Membros Atuais", value=f"{len(guild_data['membros'])}/{config_plano['membros_max']}", inline=True)
                
                try:
                    dm_embed = discord.Embed(
                        title=f"📨 Convite para {guild_data['nome']}",
                        description=f"Você foi convidado por {interaction.user.mention} para entrar na guild!",
                        color=discord.Color.gold()
                    )
                    dm_embed.add_field(name="🏰 Guild", value=guild_data["nome"], inline=True)
                    dm_embed.add_field(name="👑 Líder", value=f"<@{guild_data['lider']}>", inline=True)
                    dm_embed.add_field(name="👥 Membros", value=len(guild_data["membros"]), inline=True)
                    dm_embed.add_field(name="✅ Aceitar", value="Use `/guild_aceitar`", inline=True)
                    dm_embed.add_field(name="❌ Recusar", value="Ignore este convite", inline=True)
                    dm_embed.set_footer(text="O convite expira em 24 horas")
                    
                    await usuario.send(embed=dm_embed)
                except:
                    pass
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Erro ao enviar convite!")
            
        except Exception as e:
            print(f"❌ Erro em guild_invite: {e}")
            await interaction.followup.send("❌ Erro ao enviar convite!")

    @app_commands.command(name="guild_aceitar", description="Aceita um convite para uma guild")
    async def guild_accept(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            user_id = str(interaction.user.id)
            dados = self.carregar_dados()
            
            if self.obter_guild_por_membro(interaction.user.id):
                await interaction.followup.send("❌ Você já está em uma guild!")
                return
            
            convites_validos = []
            agora = time.time()
            
            for guild_id, guild_data in dados.items():
                if guild_id == "raids_ativas":
                    continue
                    
                for convite_id, convite_data in guild_data.get("convites", {}).items():
                    if (convite_data["usuario"] == user_id and 
                        convite_data["expiracao"] > agora):
                        convites_validos.append((guild_id, convite_id, guild_data["nome"]))
            
            if not convites_validos:
                await interaction.followup.send("❌ Nenhum convite válido encontrado!")
                return
            
            if len(convites_validos) == 1:
                guild_id, convite_id, guild_nome = convites_validos[0]
                guild_data = dados[guild_id]
                
                plano = self.obter_plano_usuario(int(guild_data["lider"]))
                config_plano = self.planos_config.get(plano, self.planos_config["gratuito"])
                
                if len(guild_data["membros"]) >= config_plano["membros_max"]:
                    await interaction.followup.send("❌ A guild atingiu o limite de membros!")
                    return
                
                guild_data["membros"][user_id] = {
                    "cargo": "Membro",
                    "entrada": time.time(),
                    "ativo": True
                }
                
                if "convites" in guild_data and convite_id in guild_data["convites"]:
                    del guild_data["convites"][convite_id]
                
                dados[guild_id] = guild_data
                
                if self.salvar_dados(dados):
                    await self.atualizar_guild_user_data(interaction.user.id, guild_id)
                    
                    embed = discord.Embed(
                        title="✅ Entrou na Guild!",
                        description=f"Você entrou em **{guild_nome}**",
                        color=discord.Color.green()
                    )
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("❌ Erro ao aceitar convite!")
            else:
                embed = discord.Embed(
                    title="📨 Convites Pendentes",
                    description="Você tem múltiplos convites. Use os botões abaixo para escolher:",
                    color=discord.Color.blue()
                )
                
                for i, (guild_id, convite_id, guild_nome) in enumerate(convites_validos[:5], 1):
                    guild_data = dados[guild_id]
                    embed.add_field(
                        name=f"{i}. {guild_nome}",
                        value=f"Líder: <@{guild_data['lider']}>\nMembros: {len(guild_data['membros'])}",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            print(f"❌ Erro em guild_accept: {e}")
            await interaction.followup.send("❌ Erro ao aceitar convite!")

    @app_commands.command(name="guild_saldo", description="Mostra o saldo do banco da guild")
    async def guild_balance(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            
            guild_id = self.obter_guild_por_membro(interaction.user.id)
            if not guild_id:
                await interaction.followup.send("❌ Você não está em uma guild!")
                return
            
            dados = self.carregar_dados()
            guild_data = dados.get(guild_id)
            
            if not guild_data:
                await interaction.followup.send("❌ Guild não encontrada!")
                return
            
            embed = discord.Embed(
                title=f"💰 Banco de {guild_data['nome']}",
                description=f"**Saldo atual:** {guild_data['banco']:,} coins",
                color=discord.Color.green()
            )
            
            multiplicador = await self.calcular_multiplicador_guild(guild_id)
            embed.add_field(name="⚡ Multiplicador Ativo", value=f"{multiplicador}x", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"❌ Erro em guild_balance: {e}")
            await interaction.followup.send("❌ Erro ao verificar saldo!")


    @app_commands.command(name="guild_depositar", description="Deposita coins no banco da guild")
    @app_commands.describe(quantidade="Quantidade de coins para depositar")
    async def guild_deposit(self, interaction: discord.Interaction, quantidade: int):
        try:
            await interaction.response.defer(ephemeral=True)
            
            guild_id = self.obter_guild_por_membro(interaction.user.id)
            if not guild_id:
                await interaction.followup.send("❌ Você não está em uma guild!")
                return
            
            if quantidade <= 0:
                await interaction.followup.send("❌ A quantidade deve ser maior que zero!")
                return
            
            dados = self.carregar_dados()
            guild_data = dados.get(guild_id)
            
            if not guild_data:
                await interaction.followup.send("❌ Guild não encontrada!")
                return
            
            coins_cog = self.bot.get_cog("FenrirCoins")
            if not coins_cog:
                await interaction.followup.send("❌ Sistema de coins indisponível no momento.")
                return

            coins_usuario = await coins_cog.obter_coins(interaction.user.id)

            if coins_usuario < quantidade:
                await interaction.followup.send(f"❌ Você não tem coins suficientes! Você tem {coins_usuario:,} coins.")
                return

            await coins_cog.remover_coins(interaction.user.id, quantidade, f"Depósito no banco da guild {guild_data['nome']}")

            guild_data["banco"] += quantidade
            dados[guild_id] = guild_data

            if self.salvar_dados(dados):
                novo_saldo = await coins_cog.obter_coins(interaction.user.id)
                embed = discord.Embed(
                    title="💰 Depósito Realizado!",
                    description=f"Você depositou **{quantidade:,} coins** no banco da guild.",
                    color=discord.Color.green()
                )
                embed.add_field(name="🏦 Saldo Anterior", value=f"{coins_usuario:,} coins", inline=True)
                embed.add_field(name="💳 Saldo Atual", value=f"{novo_saldo:,} coins", inline=True)
                embed.add_field(name="🏰 Banco da Guild", value=f"{guild_data['banco']:,} coins", inline=True)

                await interaction.followup.send(embed=embed)
            else:
                await coins_cog.adicionar_coins_sem_multiplo(interaction.user.id, quantidade, "Estorno depósito guild (falha ao salvar)")
                await interaction.followup.send("❌ Erro ao realizar depósito!")
            
        except Exception as e:
            print(f"❌ Erro em guild_deposit: {e}")
            await interaction.followup.send("❌ Erro ao realizar depósito!")

    @app_commands.command(name="guild_retirar", description="Retira coins do banco da guild")
    @app_commands.describe(quantidade="Quantidade de coins para retirar")
    async def guild_withdraw(self, interaction: discord.Interaction, quantidade: int):
        try:
            await interaction.response.defer(ephemeral=True)
            
            guild_id = self.obter_guild_por_membro(interaction.user.id)
            if not guild_id:
                await interaction.followup.send("❌ Você não está em uma guild!")
                return
            
            if quantidade <= 0:
                await interaction.followup.send("❌ A quantidade deve ser maior que zero!")
                return
            
            dados = self.carregar_dados()
            guild_data = dados.get(guild_id)
            
            if not guild_data:
                await interaction.followup.send("❌ Guild não encontrada!")
                return
            
            user_cargo = guild_data["membros"].get(str(interaction.user.id), {}).get("cargo")
            if user_cargo not in ["Líder", "Admin"]:
                await interaction.followup.send("❌ Apenas líderes e administradores podem retirar coins do banco!")
                return
            
            if guild_data["banco"] < quantidade:
                await interaction.followup.send(f"❌ O banco da guild não tem coins suficientes! Saldo: {guild_data['banco']:,} coins")
                return
            
            coins_cog = self.bot.get_cog("FenrirCoins")
            if not coins_cog:
                await interaction.followup.send("❌ Sistema de coins indisponível no momento.")
                return

            coins_usuario = await coins_cog.obter_coins(interaction.user.id)

            guild_data["banco"] -= quantidade
            dados[guild_id] = guild_data

            if self.salvar_dados(dados):
                await coins_cog.adicionar_coins_sem_multiplo(interaction.user.id, quantidade, f"Retirada do banco da guild {guild_data['nome']}")
                novo_saldo = await coins_cog.obter_coins(interaction.user.id)
                embed = discord.Embed(
                    title="💰 Retirada Realizada!",
                    description=f"Você retirou **{quantidade:,} coins** do banco da guild.",
                    color=discord.Color.green()
                )
                embed.add_field(name="🏦 Saldo Anterior", value=f"{coins_usuario:,} coins", inline=True)
                embed.add_field(name="💳 Saldo Atual", value=f"{novo_saldo:,} coins", inline=True)
                embed.add_field(name="🏰 Banco da Guild", value=f"{guild_data['banco']:,} coins", inline=True)

                await interaction.followup.send(embed=embed)
            else:
                guild_data["banco"] += quantidade
                self.salvar_dados(dados)
                await interaction.followup.send("❌ Erro ao realizar retirada!")
            
        except Exception as e:
            print(f"❌ Erro em guild_withdraw: {e}")
            await interaction.followup.send("❌ Erro ao realizar retirada!")

    @app_commands.command(name="guild_promover", description="Promove um membro da guild")
    @app_commands.describe(membro="Membro para promover")
    async def guild_promote(self, interaction: discord.Interaction, membro: discord.Member):
        try:
            await interaction.response.defer(ephemeral=True)
            
            guild_id = self.obter_guild_por_membro(interaction.user.id)
            if not guild_id:
                await interaction.followup.send("❌ Você não está em uma guild!")
                return
            
            dados = self.carregar_dados()
            guild_data = dados.get(guild_id)
            
            if not guild_data:
                await interaction.followup.send("❌ Guild não encontrada!")
                return
            
            if guild_data["lider"] != str(interaction.user.id):
                await interaction.followup.send("❌ Apenas o líder pode promover membros!")
                return
            
            user_id_str = str(membro.id)
            if user_id_str not in guild_data["membros"]:
                await interaction.followup.send("❌ Este usuário não está na sua guild!")
                return
            
            plano = self.obter_plano_usuario(int(guild_data["lider"]))
            config_plano = self.planos_config.get(plano, self.planos_config["gratuito"])
            
            admins_atuais = len([m for m in guild_data["membros"].values() if m["cargo"] == "Admin"])
            
            if guild_data["membros"][user_id_str]["cargo"] == "Membro":
                if admins_atuais >= config_plano["admins_max"]:
                    await interaction.followup.send(f"❌ Limite de {config_plano['admins_max']} administradores atingido!")
                    return
                
                guild_data["membros"][user_id_str]["cargo"] = "Admin"
                await interaction.followup.send(f"✅ {membro.mention} foi promovido a Administrador!")
            else:
                await interaction.followup.send("❌ Este membro já é um Administrador!")
            
            dados[guild_id] = guild_data
            self.salvar_dados(dados)
            
        except Exception as e:
            print(f"❌ Erro em guild_promote: {e}")
            await interaction.followup.send("❌ Erro ao promover membro!")

    @app_commands.command(name="guild_rebaixar", description="Rebaixa um membro da guild")
    @app_commands.describe(membro="Membro para rebaixar")
    async def guild_demote(self, interaction: discord.Interaction, membro: discord.Member):
        try:
            await interaction.response.defer(ephemeral=True)
            
            guild_id = self.obter_guild_por_membro(interaction.user.id)
            if not guild_id:
                await interaction.followup.send("❌ Você não está em uma guild!")
                return
            
            dados = self.carregar_dados()
            guild_data = dados.get(guild_id)
            
            if not guild_data:
                await interaction.followup.send("❌ Guild não encontrada!")
                return
            
            if guild_data["lider"] != str(interaction.user.id):
                await interaction.followup.send("❌ Apenas o líder pode rebaixar membros!")
                return
            
            user_id_str = str(membro.id)
            if user_id_str not in guild_data["membros"]:
                await interaction.followup.send("❌ Este usuário não está na sua guild!")
                return
            
            if guild_data["membros"][user_id_str]["cargo"] == "Admin":
                guild_data["membros"][user_id_str]["cargo"] = "Membro"
                await interaction.followup.send(f"✅ {membro.mention} foi rebaixado a Membro!")
            else:
                await interaction.followup.send("❌ Este membro já é um Membro!")
            
            dados[guild_id] = guild_data
            self.salvar_dados(dados)
            
        except Exception as e:
            print(f"❌ Erro em guild_demote: {e}")
            await interaction.followup.send("❌ Erro ao rebaixar membro!")

    @app_commands.command(name="guild_expulsar", description="Expulsa um membro da guild")
    @app_commands.describe(membro="Membro para expulsar")
    async def guild_kick(self, interaction: discord.Interaction, membro: discord.Member):
        try:
            await interaction.response.defer(ephemeral=True)
            
            guild_id = self.obter_guild_por_membro(interaction.user.id)
            if not guild_id:
                await interaction.followup.send("❌ Você não está em uma guild!")
                return
            
            dados = self.carregar_dados()
            guild_data = dados.get(guild_id)
            
            if not guild_data:
                await interaction.followup.send("❌ Guild não encontrada!")
                return
            
            user_cargo = guild_data["membros"].get(str(interaction.user.id), {}).get("cargo")
            if user_cargo not in ["Líder", "Admin"]:
                await interaction.followup.send("❌ Apenas líderes e administradores podem expulsar membros!")
                return
            
            user_id_str = str(membro.id)
            if user_id_str not in guild_data["membros"]:
                await interaction.followup.send("❌ Este usuário não está na sua guild!")
                return
            
            if user_id_str == guild_data["lider"]:
                await interaction.followup.send("❌ Não é possível expulsar o líder da guild!")
                return
            
            if user_cargo == "Admin" and guild_data["membros"][user_id_str]["cargo"] == "Admin":
                await interaction.followup.send("❌ Administradores não podem expulsar outros administradores!")
                return
            
            del guild_data["membros"][user_id_str]
            dados[guild_id] = guild_data
            
            if self.salvar_dados(dados):
                await self.atualizar_guild_user_data(membro.id, None)
                await interaction.followup.send(f"✅ {membro.mention} foi expulso da guild!")
            else:
                await interaction.followup.send("❌ Erro ao expulsar membro!")
            
        except Exception as e:
            print(f"❌ Erro em guild_kick: {e}")
            await interaction.followup.send("❌ Erro ao expulsar membro!")

    @app_commands.command(name="guild_transferir", description="Transfere a liderança da guild")
    @app_commands.describe(novo_lider="Novo líder da guild")
    async def guild_transfer(self, interaction: discord.Interaction, novo_lider: discord.Member):
        try:
            await interaction.response.defer(ephemeral=True)
            
            guild_id = self.obter_guild_por_membro(interaction.user.id)
            if not guild_id:
                await interaction.followup.send("❌ Você não está em uma guild!")
                return
            
            dados = self.carregar_dados()
            guild_data = dados.get(guild_id)
            
            if not guild_data:
                await interaction.followup.send("❌ Guild não encontrada!")
                return
            
            if guild_data["lider"] != str(interaction.user.id):
                await interaction.followup.send("❌ Apenas o líder atual pode transferir a liderança!")
                return
            
            novo_lider_id = str(novo_lider.id)
            if novo_lider_id not in guild_data["membros"]:
                await interaction.followup.send("❌ Este usuário não está na sua guild!")
                return
            
            guild_data["lider"] = novo_lider_id
            guild_data["membros"][novo_lider_id]["cargo"] = "Líder"
            guild_data["membros"][str(interaction.user.id)]["cargo"] = "Admin"
            
            dados[guild_id] = guild_data
            
            if self.salvar_dados(dados):
                await interaction.followup.send(f"✅ Liderança transferida para {novo_lider.mention}!")
            else:
                await interaction.followup.send("❌ Erro ao transferir liderança!")
            
        except Exception as e:
            print(f"❌ Erro em guild_transfer: {e}")
            await interaction.followup.send("❌ Erro ao transferir liderança!")

    @app_commands.command(name="guild_config", description="Configurações da guild")
    @app_commands.describe(motto="Novo motto da guild", emoji="Novo emoji da guild")
    async def guild_config(self, interaction: discord.Interaction, motto: str = None, emoji: str = None):
        try:
            await interaction.response.defer(ephemeral=True)
            
            guild_id = self.obter_guild_por_membro(interaction.user.id)
            if not guild_id:
                await interaction.followup.send("❌ Você não está em uma guild!")
                return
            
            dados = self.carregar_dados()
            guild_data = dados.get(guild_id)
            
            if not guild_data:
                await interaction.followup.send("❌ Guild não encontrada!")
                return
            
            user_cargo = guild_data["membros"].get(str(interaction.user.id), {}).get("cargo")
            if user_cargo not in ["Líder", "Admin"]:
                await interaction.followup.send("❌ Apenas líderes e administradores podem configurar la guild!")
                return
            
            embed = discord.Embed(
                title="⚙️ Configurações da Guild",
                color=discord.Color.blue()
            )
            
            if motto:
                if len(motto) > 100:
                    await interaction.followup.send("❌ O motto deve ter no máximo 100 caracteres!")
                    return
                guild_data["motto"] = motto
                embed.add_field(name="📝 Motto", value=f"Definido para: {motto}", inline=False)
            
            if emoji:
                guild_data["emoji"] = emoji
                embed.add_field(name="🎨 Emoji", value=f"Definido para: {emoji}", inline=False)
            
            if not motto and not emoji:
                embed.add_field(name="📝 Motto Atual", value=guild_data.get("motto", "Não definido"), inline=True)
                embed.add_field(name="🎨 Emoji Atual", value=guild_data.get("emoji", "Não definido"), inline=True)
                embed.add_field(name="💡 Como usar", value="Use `/guild_config motto: [texto] emoji: [emoji]` para alterar", inline=False)
            
            dados[guild_id] = guild_data
            
            if self.salvar_dados(dados):
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Erro ao salvar configurações!")
            
        except Exception as e:
            print(f"❌ Erro em guild_config: {e}")
            await interaction.followup.send("❌ Erro ao configurar guild!")

    @app_commands.command(name="guild_deletar", description="Deleta a guild (apenas líder)")
    async def guild_delete(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            guild_id = self.obter_guild_por_membro(interaction.user.id)
            if not guild_id:
                await interaction.followup.send("❌ Você não está em uma guild!")
                return
            
            dados = self.carregar_dados()
            guild_data = dados.get(guild_id)
            
            if not guild_data:
                await interaction.followup.send("❌ Guild não encontrada!")
                return
            
            if guild_data["lider"] != str(interaction.user.id):
                await interaction.followup.send("❌ Apenas o líder pode deletar a guild!")
                return
            
            del dados[guild_id]
            
            if self.salvar_dados(dados):
                for user_id in guild_data["membros"]:
                    await self.atualizar_guild_user_data(int(user_id), None)
                
                await interaction.followup.send(f"✅ Guild **{guild_data['nome']}** deletada!")
            else:
                await interaction.followup.send("❌ Erro ao deletar guild!")
            
        except Exception as e:
            print(f"❌ Erro em guild_delete: {e}")
            await interaction.followup.send("❌ Erro ao deletar guild!")

    @app_commands.command(name="guild_raid", description="Inicia uma raid contra outra guild")
    @app_commands.describe(guild_alvo="Nome da guild que você deseja raidar")
    async def guild_raid(self, interaction: discord.Interaction, guild_alvo: str):
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            
            raid_cog = self.bot.get_cog("GuildAllianceRaidSystem")
            if not raid_cog:
                await interaction.followup.send("❌ Sistema de raids não está disponível no momento.", ephemeral=True)
                return
            
            guild_atacante_id = raid_cog.obter_guild_por_membro(interaction.user.id)
            if not guild_atacante_id:
                await interaction.followup.send("❌ Você precisa estar em uma guild para iniciar uma raid!", ephemeral=True)
                return
            
            dados = raid_cog.carregar_dados()
            guild_atacante = dados.get(guild_atacante_id)
            
            if not guild_atacante:
                await interaction.followup.send("❌ Sua guild não foi encontrada!", ephemeral=True)
                return
            
            cargo_usuario = guild_atacante["membros"].get(str(interaction.user.id), {}).get("cargo")
            if cargo_usuario not in ["Líder", "Admin"]:
                await interaction.followup.send("❌ Apenas líderes e administradores podem iniciar raids!", ephemeral=True)
                return
            
            if guild_atacante.get("xp", 0) < 500:
                await interaction.followup.send(
                    "❌ Sua guild precisa ter pelo menos **500 de poder (XP)** para iniciar uma raid!\n"
                    f"**Poder atual:** {guild_atacante.get('xp', 0)}",
                    ephemeral=True
                )
                return
            
            if guild_atacante.get("banco", 0) < 10000:
                await interaction.followup.send(
                    "❌ Seu banco da guild precisa ter pelo menos **10.000 coins** para raidar!\n"
                    f"**Coins atuais:** {guild_atacante.get('banco', 0)}",
                    ephemeral=True
                )
                return
            
            guild_alvo_encontrada = None
            for guild_id, guild_data in dados.items():
                if guild_id != "raids_ativas" and guild_data.get("nome", "").lower() == guild_alvo.lower():
                    guild_alvo_encontrada = (guild_id, guild_data)
                    break
            
            if not guild_alvo_encontrada:
                await interaction.followup.send("❌ Guild alvo não encontrada!", ephemeral=True)
                return
            
            guild_alvo_id, guild_alvo_data = guild_alvo_encontrada
            
            if guild_atacante_id == guild_alvo_id:
                await interaction.followup.send("❌ Você não pode raidar sua própria guild!", ephemeral=True)
                return

            _cfg = getattr(self.bot, "config", None)
            _raid_cd = (_cfg.get("guild_raid_cooldown_s") if _cfg else None) or 86400
            ultima_raid = guild_alvo_data.get("ultima_raid", 0)
            if time.time() - ultima_raid < _raid_cd:
                tempo_restante = _raid_cd - (time.time() - ultima_raid)
                horas = int(tempo_restante // 3600)
                minutos = int((tempo_restante % 3600) // 60)
                await interaction.followup.send(f"❌ Esta guild foi raidada recentemente! Tente novamente em {horas}h {minutos}m", ephemeral=True)
                return
            
            if len(guild_atacante["membros"]) < 5:
                await interaction.followup.send("❌ Sua guild precisa ter pelo menos 5 membros para raidar!", ephemeral=True)
                return
            
            if guild_alvo_data.get("xp", 0) < 100:
                await interaction.followup.send(
                    "❌ A guild alvo é muito fraca para ser raidada!\n"
                    f"**Poder da guild alvo:** {guild_alvo_data.get('xp', 0)} (mínimo: 100)",
                    ephemeral=True
                )
                return

            if len(guild_alvo_data.get("membros", {})) < 3:
                await interaction.followup.send("❌ A guild alvo é muito pequena para ser raidada (mínimo 3 membros)!", ephemeral=True)
                return

            await raid_cog.iniciar_raid(interaction, guild_alvo)
            
        except Exception as e:
            print(f"❌ Erro em guild_raid: {e}")
            await interaction.followup.send("❌ Erro ao iniciar raid!", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(GuildSystem(bot))