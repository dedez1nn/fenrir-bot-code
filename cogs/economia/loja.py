import time
from typing import Any, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands

from repositories import items as items_repo


def _db_row_to_item(row: Dict[str, Any]) -> Dict[str, Any]:
    """Converte uma linha do DB para o formato dict usado na loja."""
    criado_em = row.get("criado_em")
    return {
        "id": row["id"],
        "nome": row["nome"],
        "preco": row["preco"],
        "descricao": row.get("descricao") or "",
        "cooldown_h": float(row.get("cooldown_h") or 0),
        "criado_por": row["criado_por"],
        "criado_em": criado_em.timestamp() if criado_em else None,
    }


class LojaView(discord.ui.View):
    def __init__(self, loja_cog, page=0):
        super().__init__(timeout=120)
        self.loja_cog = loja_cog
        self.page = page
        self.itens_por_pagina = 5

        self.loja_data = self.loja_cog.loja_data
        self.total_pages = max(
            1,
            (len(self.loja_data["itens"]) + self.itens_por_pagina - 1)
            // self.itens_por_pagina,
        )
        self.update_buttons()

    def update_buttons(self):
        self.botao_anterior.disabled = self.page == 0
        self.botao_proximo.disabled = self.page >= self.total_pages - 1
        self.contador.label = f"Página {self.page + 1}/{self.total_pages}"

    def create_loja_embed(self):
        start_index = self.page * self.itens_por_pagina
        itens_pagina = self.loja_data["itens"][start_index : start_index + self.itens_por_pagina]

        embed = discord.Embed(
            title="🏪 Loja da Alcateia",
            description=(
                "💎 **Itens Disponíveis para Compra**\n\n"
                "Use `/comprar [número]` para adquirir um item!\n"
                "**Número = Posição na lista (1, 2, 3...)**"
            ),
            color=discord.Color.gold(),
        )

        if not itens_pagina:
            embed.add_field(
                name="📭 Nenhum item nesta página",
                value="Não há itens para mostrar nesta página.",
                inline=False,
            )
        else:
            for i, item in enumerate(itens_pagina, start=1):
                numero_sequencial = (self.page * self.itens_por_pagina) + i
                descricao = item["descricao"].replace("\\n", "\n")
                embed.add_field(
                    name=f"`#{numero_sequencial}` {item['nome']} - 💎 {item['preco']} coins",
                    value=f"{descricao}\n**ID:** `#{item['id']}`\n──────────────",
                    inline=False,
                )

        total_itens = len(self.loja_data["itens"])
        embed.set_footer(
            text=(
                f"Página {self.page + 1}/{self.total_pages} • "
                f"{total_itens} itens no total • Números: 1-{total_itens}"
            )
        )
        return embed

    @discord.ui.button(label="◀️ Anterior", style=discord.ButtonStyle.secondary)
    async def botao_anterior(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if self.page > 0:
                self.page -= 1
                self.update_buttons()
                await interaction.response.edit_message(embed=self.create_loja_embed(), view=self)
            else:
                await interaction.response.defer()
        except Exception as e:
            print(f"❌ Erro no botão anterior: {e}")
            await interaction.response.defer()

    @discord.ui.button(label="Página 1/1", style=discord.ButtonStyle.primary, disabled=True)
    async def contador(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

    @discord.ui.button(label="Próximo ▶️", style=discord.ButtonStyle.secondary)
    async def botao_proximo(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if self.page < self.total_pages - 1:
                self.page += 1
                self.update_buttons()
                await interaction.response.edit_message(embed=self.create_loja_embed(), view=self)
            else:
                await interaction.response.defer()
        except Exception as e:
            print(f"❌ Erro no botão próximo: {e}")
            await interaction.response.defer()

    @discord.ui.button(label="🔄 Atualizar", style=discord.ButtonStyle.success)
    async def botao_atualizar(self, interaction: discord.Interaction):
        try:
            await self.loja_cog.recarregar()
            self.loja_data = self.loja_cog.loja_data
            self.total_pages = max(
                1,
                (len(self.loja_data["itens"]) + self.itens_por_pagina - 1)
                // self.itens_por_pagina,
            )
            if self.page >= self.total_pages:
                self.page = max(0, self.total_pages - 1)
            self.update_buttons()

            await interaction.response.edit_message(embed=self.create_loja_embed(), view=self)
            await self.loja_cog.enviar_log_loja(
                interaction,
                "Loja Atualizada",
                f"**Ação:** Atualizou a visualização da loja\n**Página atual:** {self.page + 1}",
                discord.Color.blue(),
            )
        except Exception as e:
            print(f"❌ Erro no botão atualizar: {e}")
            await interaction.response.send_message("❌ Erro ao atualizar a loja.", ephemeral=True)

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
            if hasattr(self, "message"):
                await self.message.edit(view=self)
        except Exception as e:
            print(f"⚠️ Erro ao desativar botões: {e}")


class LojaCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ARQUIVO_LOJA = "data/loja_data.json"
        self.loja_data: Dict[str, Any] = {"itens": []}

    async def cog_load(self) -> None:
        await self.recarregar()

    # ── Carga de dados ────────────────────────────────────────────────────────

    async def recarregar(self) -> None:
        if self.bot.db:
            rows = await items_repo.get_all(self.bot.db)
            self.loja_data = {"itens": [_db_row_to_item(r) for r in rows]}
        else:
            self.loja_data = self.carregar_dados()

    def carregar_dados(self) -> Dict[str, Any]:
        import json, os
        try:
            if os.path.exists(self.ARQUIVO_LOJA):
                with open(self.ARQUIVO_LOJA, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    itens = data.get("itens", [])
                elif isinstance(data, list):
                    itens = data
                else:
                    itens = []
                itens = sorted(itens, key=lambda x: x.get("preco", 0), reverse=True)
                return {"itens": itens, "proximo_id": data.get("proximo_id", len(itens) + 1) if isinstance(data, dict) else len(itens) + 1}
            return {"itens": [], "proximo_id": 1}
        except Exception as e:
            print(f"❌ Erro ao carregar loja JSON: {e}")
            return {"itens": [], "proximo_id": 1}

    def salvar_dados(self) -> None:
        import json
        try:
            with open(self.ARQUIVO_LOJA, "w", encoding="utf-8") as f:
                json.dump(self.loja_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Erro ao salvar loja JSON: {e}")

    def ordenar_itens(self) -> None:
        self.loja_data["itens"] = sorted(
            self.loja_data["itens"], key=lambda x: x.get("preco", 0), reverse=True
        )
        self.salvar_dados()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def encontrar_item_por_posicao(self, posicao: int) -> Optional[Dict[str, Any]]:
        itens = self.loja_data.get("itens", [])
        if posicao < 1 or posicao > len(itens):
            return None
        return itens[posicao - 1]

    async def verificar_e_remover_coins(self, user_id: int, preco: int, item_nome: str) -> bool:
        try:
            coins_cog = self.bot.get_cog("FenrirCoins")
            if not coins_cog:
                return False
            saldo = await coins_cog.obter_coins(user_id)
            if saldo < preco:
                return False
            await coins_cog.remover_coins(user_id, preco, f"Compra: {item_nome}")
            return True
        except Exception as e:
            print(f"❌ Erro ao verificar/remover coins: {e}")
            return False

    async def obter_preco_item(self, item_id: int) -> int:
        item = self.encontrar_item_por_posicao(item_id)
        return item["preco"] if item else 0

    async def enviar_log_loja(
        self,
        interaction: discord.Interaction,
        acao: str,
        descricao: str,
        cor=discord.Color.gold(),
    ):
        try:
            canal_id = (
                self.bot.config.get("coins_log_channel_id") if self.bot.config else None
            )
            canal_log = self.bot.get_channel(canal_id) if canal_id else None
            if canal_log:
                embed_log = discord.Embed(
                    title=f"🏪 Loja - {acao}",
                    description=f"{descricao}\n\n**Usuário:** {interaction.user.mention}",
                    color=cor,
                    timestamp=discord.utils.utcnow(),
                )
                embed_log.set_thumbnail(url=interaction.user.display_avatar.url)
                await canal_log.send(embed=embed_log)
        except Exception as e:
            print(f"❌ Erro ao enviar log loja: {e}")

    # ── Comandos ──────────────────────────────────────────────────────────────

    @app_commands.command(name="loja", description="Ver a loja de itens disponíveis")
    async def loja(self, interaction: discord.Interaction):
        if await self.bot.guard_channel(interaction):
            return
        try:
            await self.recarregar()
            if not self.loja_data["itens"]:
                embed = discord.Embed(
                    title="🏪 Loja Vazia",
                    description=(
                        "Não há itens disponíveis no momento.\n"
                        "Os administradores podem adicionar itens usando `/adicionar_item`"
                    ),
                    color=discord.Color.orange(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            view = LojaView(self)
            embed = view.create_loja_embed()
            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()
        except Exception as e:
            print(f"❌ Erro no comando /loja: {e}")
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao abrir a loja. Tente novamente.", ephemeral=True
            )

    @app_commands.command(name="comprar", description="Comprar um item da loja")
    @app_commands.describe(item_id="Número do item na lista da loja")
    async def comprar(self, interaction: discord.Interaction, item_id: int):
        if await self.bot.guard_channel(interaction):
            return
        try:
            print(f"🛒 COMPRAR: user={interaction.user.id} posicao={item_id}")
            await interaction.response.defer(ephemeral=False, thinking=True)

            itens = self.loja_data.get("itens", [])
            if item_id < 1 or item_id > len(itens):
                await interaction.followup.send(
                    "❌ **ID do item inválido!**\nVerifique a lista de itens na loja.",
                    ephemeral=False,
                )
                return

            item = self.encontrar_item_por_posicao(item_id)
            if not item:
                await interaction.followup.send("❌ **Item não encontrado!**", ephemeral=False)
                return

            preco_item = item["preco"]
            item_nome = item["nome"]
            item_db_id = item["id"]
            cooldown_h = item.get("cooldown_h", 0)
            cooldown_secs = float(cooldown_h) * 3600 if cooldown_h and cooldown_h > 0 else None
            user_id = interaction.user.id

            coins_cog = self.bot.get_cog("FenrirCoins")
            saldo_anterior = await coins_cog.obter_coins(user_id) if coins_cog else 0

            if not await self.verificar_e_remover_coins(user_id, preco_item, item_nome):
                await interaction.followup.send(
                    f"❌ **Saldo insuficiente!**\n"
                    f"💎 Precisa de **{preco_item} coins** para **{item_nome}**\n"
                    f"💰 Saldo atual: **{saldo_anterior} coins**\n\n"
                    "💡 Ganhe coins com `/daily`, mensagens ou calls de voz.",
                    ephemeral=False,
                )
                return

            saldo_atual = await coins_cog.obter_coins(user_id) if coins_cog else 0

            compra_cog = self.bot.get_cog("CompraCog")
            if compra_cog is None:
                if coins_cog:
                    await coins_cog.adicionar_coins(
                        user_id, preco_item, "Devolução - CompraCog não encontrado"
                    )
                await interaction.followup.send(
                    "❌ **Erro ao processar compra!** Tente novamente.", ephemeral=False
                )
                return

            resultado = await compra_cog.processar_compra(
                interaction,
                item_id,
                user_id,
                item_nome,
                item_db_id=item_db_id,
                cooldown_secs=cooldown_secs,
            )

            if resultado:
                await self.enviar_log_loja(
                    interaction,
                    "Compra Realizada",
                    f"**Item:** {item_nome}\n"
                    f"**Preço:** {preco_item} coins\n"
                    f"**ID DB:** {item_db_id} | **Posição:** {item_id}\n"
                    f"**Saldo anterior:** {saldo_anterior} coins\n"
                    f"**Saldo atual:** {saldo_atual} coins",
                    discord.Color.green(),
                )
                await interaction.followup.send(
                    f"✅ **Compra realizada com sucesso!**\n"
                    f"🛒 **{item_nome}**\n"
                    f"💳 **Saldo atual:** {saldo_atual} coins\n",
                    ephemeral=True,
                )
            else:
                if coins_cog:
                    await coins_cog.adicionar_coins(
                        user_id, preco_item, "Devolução - Falha no processamento"
                    )
                await interaction.followup.send(
                    "❌ **Erro ao processar sua compra!**\n"
                    "Suas coins foram devolvidas. Tente novamente.",
                    ephemeral=False,
                )
        except Exception as e:
            print(f"❌ ERRO COMPRAR: {e}")
            import traceback; traceback.print_exc()
            try:
                coins_cog = self.bot.get_cog("FenrirCoins")
                if coins_cog:
                    await coins_cog.adicionar_coins(user_id, preco_item, "Devolução - Erro")
                await interaction.followup.send(
                    "❌ **Erro ao processar compra!** Suas coins foram devolvidas.",
                    ephemeral=False,
                )
            except Exception as fe:
                print(f"❌ Erro ao enviar followup: {fe}")

    @app_commands.command(name="adicionar_item", description="Adicionar um item à loja (ADM)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        nome="Nome do item",
        preco="Preço em coins",
        descricao="Descrição breve do item",
        cooldown_h="Cooldown em horas após compra (0 = sem cooldown)",
    )
    async def adicionar_item(
        self,
        interaction: discord.Interaction,
        nome: str,
        preco: int,
        descricao: str,
        cooldown_h: float = 0.0,
    ):
        if preco <= 0:
            await interaction.response.send_message(
                "❌ O preço deve ser maior que 0!", ephemeral=True
            )
            return
        if len(nome) > 50:
            await interaction.response.send_message(
                "❌ O nome deve ter no máximo 50 caracteres!", ephemeral=True
            )
            return
        if len(descricao) > 200:
            await interaction.response.send_message(
                "❌ A descrição deve ter no máximo 200 caracteres!", ephemeral=True
            )
            return

        if self.bot.db:
            db_row = await items_repo.create(
                self.bot.db,
                nome=nome,
                preco=preco,
                descricao=descricao,
                cooldown_h=cooldown_h,
                criado_por=interaction.user.id,
            )
            novo_item = _db_row_to_item(db_row)
            self.loja_data["itens"].append(novo_item)
            self.loja_data["itens"].sort(key=lambda x: x["preco"], reverse=True)
        else:
            novo_item = {
                "id": self.loja_data.get("proximo_id", 1),
                "nome": nome,
                "preco": preco,
                "descricao": descricao,
                "cooldown_h": cooldown_h,
                "criado_por": interaction.user.id,
                "criado_em": time.time(),
            }
            self.loja_data.setdefault("itens", []).append(novo_item)
            self.loja_data["proximo_id"] = self.loja_data.get("proximo_id", 1) + 1
            self.ordenar_itens()

        posicao = next(
            (i + 1 for i, it in enumerate(self.loja_data["itens"]) if it["id"] == novo_item["id"]),
            "?",
        )

        embed = discord.Embed(
            title="✅ Item Adicionado à Loja!",
            description=f"**{nome}** foi adicionado com sucesso!",
            color=discord.Color.green(),
        )
        embed.add_field(name="💰 Preço", value=f"💎 {preco} coins", inline=True)
        embed.add_field(name="📝 ID", value=f"`#{novo_item['id']}`", inline=True)
        if cooldown_h > 0:
            embed.add_field(name="⏰ Cooldown", value=f"{cooldown_h}h", inline=True)
        embed.add_field(name="📋 Descrição", value=descricao, inline=False)
        embed.add_field(name="📍 Posição", value=f"`#{posicao}` (após ordenação)", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.enviar_log_loja(
            interaction,
            "Item Adicionado",
            f"**Item:** {nome}\n**Preço:** {preco} coins\n"
            f"**Cooldown:** {cooldown_h}h\n**Posição:** #{posicao}",
            discord.Color.green(),
        )

    @app_commands.command(name="remover_item", description="Remover um item da loja (ADM)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        numero_item="Número do item a ser removido (1, 2, 3...)",
        motivo="Motivo da remoção (opcional)",
    )
    async def remover_item(
        self,
        interaction: discord.Interaction,
        numero_item: int,
        motivo: str = "Não especificado",
    ):
        item_encontrado = self.encontrar_item_por_posicao(numero_item)
        if not item_encontrado:
            await interaction.response.send_message(
                f"❌ Item `#{numero_item}` não encontrado na loja!", ephemeral=True
            )
            await self.enviar_log_loja(
                interaction,
                "Tentativa de Remoção - Erro",
                f"Tentou remover item #{numero_item} — não encontrado.",
                discord.Color.red(),
            )
            return

        if self.bot.db:
            await items_repo.delete_one(self.bot.db, item_encontrado["id"])
            self.loja_data["itens"] = [
                i for i in self.loja_data["itens"] if i["id"] != item_encontrado["id"]
            ]
        else:
            self.loja_data["itens"] = [
                i for i in self.loja_data["itens"] if i["id"] != item_encontrado["id"]
            ]
            self.salvar_dados()

        embed = discord.Embed(
            title="✅ Item Removido da Loja!",
            description=f"**{item_encontrado['nome']}** foi removido com sucesso!",
            color=discord.Color.orange(),
        )
        embed.add_field(name="💰 Preço", value=f"💎 {item_encontrado['preco']} coins", inline=True)
        embed.add_field(name="📍 Posição removida", value=f"`#{numero_item}`", inline=True)
        embed.add_field(name="📋 Motivo", value=motivo, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.enviar_log_loja(
            interaction,
            "Item Removido",
            f"**Item:** {item_encontrado['nome']}\n"
            f"**Preço:** {item_encontrado['preco']} coins\n"
            f"**Posição:** #{numero_item}\n**Motivo:** {motivo}",
            discord.Color.orange(),
        )

    @app_commands.command(name="limpar_loja", description="Remover TODOS os itens da loja (ADM)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(motivo="Motivo da limpeza (opcional)")
    async def limpar_loja(
        self, interaction: discord.Interaction, motivo: str = "Não especificado"
    ):
        if not self.loja_data["itens"]:
            await interaction.response.send_message("❌ A loja já está vazia!", ephemeral=True)
            return

        quantidade = len(self.loja_data["itens"])
        itens_removidos = list(self.loja_data["itens"])

        if self.bot.db:
            await items_repo.delete_all(self.bot.db)
        else:
            self.salvar_dados()  # save vazio depois de limpar

        self.loja_data["itens"] = []
        if not self.bot.db:
            self.salvar_dados()

        embed = discord.Embed(
            title="🧹 Loja Limpa!",
            description=f"**{quantidade} itens** foram removidos da loja!",
            color=discord.Color.red(),
        )
        embed.add_field(name="📋 Motivo", value=motivo, inline=False)
        preview = itens_removidos[:5]
        lista = "\n".join(f"• {i['nome']} (💎 {i['preco']})" for i in preview)
        if quantidade > 5:
            lista += f"\n• ... e mais {quantidade - 5} itens"
        embed.add_field(name="🗑️ Itens Removidos", value=lista, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.enviar_log_loja(
            interaction,
            "Loja Limpa",
            f"**Itens removidos:** {quantidade}\n**Motivo:** {motivo}",
            discord.Color.red(),
        )

    @adicionar_item.error
    @remover_item.error
    @limpar_loja.error
    async def comandos_adm_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você não tem permissão de administrador para usar este comando.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(LojaCog(bot))
