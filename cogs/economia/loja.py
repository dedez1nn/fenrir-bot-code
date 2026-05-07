import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import time

class LojaView(discord.ui.View):
    def __init__(self, loja_cog, page=0):
        super().__init__(timeout=120)
        self.loja_cog = loja_cog
        self.page = page
        self.itens_por_pagina = 5
        
        self.loja_data = self.loja_cog.loja_data
        self.total_pages = max(1, (len(self.loja_data["itens"]) + self.itens_por_pagina - 1) // self.itens_por_pagina)
        
        self.update_buttons()
        
    def update_buttons(self):
        """Atualiza o estado dos botões baseado na página atual"""
        self.botao_anterior.disabled = self.page == 0
        self.botao_proximo.disabled = self.page >= self.total_pages - 1
        self.contador.label = f"Página {self.page + 1}/{self.total_pages}"

    def create_loja_embed(self):
        start_index = self.page * self.itens_por_pagina
        end_index = start_index + self.itens_por_pagina
        itens_pagina = self.loja_data["itens"][start_index:end_index]

        embed = discord.Embed(
            title="🏪 Loja da Alcateia",
            description="💎 **Itens Disponíveis para Compra**\n\nUse `/comprar [número]` para adquirir um item!\n**Número = Posição na lista (1, 2, 3...)**",
            color=discord.Color.gold()
        )

        if not itens_pagina:
            embed.add_field(
                name="📭 Nenhum item nesta página",
                value="Não há itens para mostrar nesta página.",
                inline=False
            )
        else:
            for i, item in enumerate(itens_pagina, start=1):
                numero_sequencial = (self.page * self.itens_por_pagina) + i
                descricao = item["descricao"].replace("\\n", "\n")
                
                embed.add_field(
                    name=f"`#{numero_sequencial}` {item['nome']} - 💎 {item['preco']} coins",
                    value=f"{descricao}\n**ID:** `#{item['id']}`\n──────────────",
                    inline=False
                )

        total_itens = len(self.loja_data["itens"])
        embed.set_footer(
            text=f"Página {self.page + 1}/{self.total_pages} • {total_itens} itens no total • Números: 1-{total_itens}"
        )
        
        return embed

    @discord.ui.button(label="◀️ Anterior", style=discord.ButtonStyle.secondary)
    async def botao_anterior(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if self.page > 0:
                self.page -= 1
                self.update_buttons()
                embed = self.create_loja_embed()
                await interaction.response.edit_message(embed=embed, view=self)
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
                embed = self.create_loja_embed()
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.defer()
        except Exception as e:
            print(f"❌ Erro no botão próximo: {e}")
            await interaction.response.defer()

    @discord.ui.button(label="🔄 Atualizar", style=discord.ButtonStyle.success)
    async def botao_atualizar(self, interaction: discord.Interaction):
        try:
            self.loja_data = self.loja_cog.carregar_dados()
            self.total_pages = max(1, (len(self.loja_data["itens"]) + self.itens_por_pagina - 1) // self.itens_por_pagina)
            
            if self.page >= self.total_pages and self.total_pages > 0:
                self.page = self.total_pages - 1
            
            self.update_buttons()
            embed = self.create_loja_embed()
            
            await interaction.response.edit_message(embed=embed, view=self)
            
            await self.loja_cog.enviar_log_loja(
                interaction,
                "Loja Atualizada",
                f"**Ação:** Atualizou a visualização da loja\n**Página atual:** {self.page + 1}",
                discord.Color.blue()
            )
        except Exception as e:
            print(f"❌ Erro no botão atualizar: {e}")
            await interaction.response.send_message("❌ Erro ao atualizar a loja.", ephemeral=True)

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
            if hasattr(self, 'message'):
                await self.message.edit(view=self)
        except Exception as e:
            print(f"⚠️ Erro ao desativar botões: {e}")


class LojaCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ARQUIVO_LOJA = "data/loja_data.json"
        self.loja_data = self.carregar_dados()
        self.canal_log_loja = 1427491600115699874

    def carregar_dados(self):
        try:
            if os.path.exists(self.ARQUIVO_LOJA):
                with open(self.ARQUIVO_LOJA, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "itens" not in data:
                        data["itens"] = []
                    if "proximo_id" not in data:
                        data["proximo_id"] = 1
                    
                    data["itens"] = sorted(data["itens"], key=lambda x: x["preco"], reverse=True)
                    
                    return data
            return {"itens": [], "proximo_id": 1}
        except Exception as e:
            print(f"❌ Erro ao carregar dados da loja: {e}")
            return {"itens": [], "proximo_id": 1}

    def salvar_dados(self):
        try:
            with open(self.ARQUIVO_LOJA, "w", encoding="utf-8") as f:
                json.dump(self.loja_data, f, indent=4, ensure_ascii=False)  
        except Exception as e:
            print(f"❌ Erro ao salvar dados da loja: {e}")

    def ordenar_itens(self):
        self.loja_data["itens"] = sorted(self.loja_data["itens"], key=lambda x: x["preco"], reverse=True)
        self.salvar_dados()
        
    async def verificar_e_remover_coins(self, user_id: int, preco: int, item_nome: str) -> bool:
        try:
            coins_cog = self.bot.get_cog("FenrirCoins")
            if not coins_cog:
                print("❌ Cog FenrirCoins não encontrado")
                return False
            
            saldo_atual = await coins_cog.obter_coins(user_id)
            print(f"💰 Verificando saldo: User {user_id}, Saldo: {saldo_atual}, Preço: {preco}")
            
            if saldo_atual < preco:
                print(f"❌ Saldo insuficiente: {saldo_atual} < {preco}")
                return False
            
            await coins_cog.remover_coins(user_id, preco, f"Compra: {item_nome}")
            print(f"✅ Coins removidas: {preco} do user {user_id}")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao verificar/remover coins: {e}")
            return False


    def encontrar_item_por_posicao(self, posicao: int):
        if posicao < 1 or posicao > len(self.loja_data["itens"]):
            return None
        return self.loja_data["itens"][posicao - 1]

    async def enviar_log_loja(self, interaction, acao, descricao, cor=discord.Color.gold()):
        try:
            canal_log = self.bot.get_channel(self.canal_log_loja)
            if canal_log:
                embed_log = discord.Embed(
                    title=f"🏪 Loja - {acao}",
                    description=f"{descricao}\n\n**Usuário:** {interaction.user.mention}",
                    color=cor,
                    timestamp=discord.utils.utcnow()
                )
                embed_log.set_thumbnail(url=interaction.user.display_avatar.url)
                await canal_log.send(embed=embed_log)
        except Exception as e:
            print(f"❌ Erro ao enviar log: {e}")

    @app_commands.command(name="loja", description="Ver a loja de itens disponíveis")
    async def loja(self, interaction: discord.Interaction):
        
        if interaction.channel.id != 1426205118293868748 and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(f"❌ Ei, {interaction.user.mention}, use esse **comando** apenas em {self.bot.get_channel(1426205118293868748).mention} !", ephemeral=True)
            return
        
        try:
            self.loja_data = self.carregar_dados()
            
            if not self.loja_data["itens"]:
                embed = discord.Embed(
                    title="🏪 Loja Vazia",
                    description="Não há itens disponíveis no momento.\nOs administradores podem adicionar itens usando `/adicionar_item`",
                    color=discord.Color.orange()
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
                "❌ Ocorreu um erro ao abrir a loja. Tente novamente.",
                ephemeral=True
            )

    async def obter_preco_item(self, item_id: int) -> int:
        item = self.encontrar_item_por_posicao(item_id)
        return item["preco"] if item else 0

    @app_commands.command(name="comprar", description="Comprar um item da loja")
    @app_commands.describe(item_id="ID do item que deseja comprar")
    async def comprar(self, interaction: discord.Interaction, item_id: int):
        
        if interaction.channel.id != 1426205118293868748 and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(f"❌ Ei, {interaction.user.mention}, use esse **comando** apenas em {self.bot.get_channel(1426205118293868748).mention} !", ephemeral=True)
            return
        
        try:
            print(f"🛒 COMPRAR: Iniciando compra - User: {interaction.user.id}, Item: {item_id}")

            await interaction.response.defer(ephemeral=False, thinking=True)
            print("✅ Comprar: Resposta deferida")

            if item_id < 1 or item_id > len(self.loja_data["itens"]):
                await interaction.followup.send(
                    "❌ **ID do item inválido!**\n"
                    "Verifique a lista de itens na loja e tente novamente.",
                    ephemeral=False
                )
                return
            
            item = self.encontrar_item_por_posicao(item_id)
            if not item:
                await interaction.followup.send(
                    "❌ **Item não encontrado!**\n"
                    "Verifique a lista de itens na loja e tente novamente.",
                    ephemeral=False
                )
                return
                
            preco_item = item["preco"]
            item_nome = item["nome"]
            user_id = interaction.user.id
            
            coins_cog = self.bot.get_cog("FenrirCoins")
            saldo_anterior = await coins_cog.obter_coins(user_id) if coins_cog else 0
            
            print(f"💰 Saldo anterior do usuário {user_id}: {saldo_anterior} coins")
            
            coins_suficientes = await self.verificar_e_remover_coins(user_id, preco_item, item_nome)
            
            if not coins_suficientes:
                await interaction.followup.send(
                    f"❌ **Saldo insuficiente!**\n"
                    f"💎 Você precisa de **{preco_item} coins** para comprar **{item_nome}**\n"
                    f"💰 Seu saldo atual: **{saldo_anterior} coins**\n\n"
                    f"💡 Ganhe mais coins usando:\n"
                    f"• `/daily` - Recompensa diária\n"
                    f"• Enviando mensagens no chat\n"
                    f"• Participando de calls de voz",
                    ephemeral=False
                )
                return

            saldo_atual = await coins_cog.obter_coins(user_id) if coins_cog else 0
            print(f"💰 Saldo atual do usuário {user_id}: {saldo_atual} coins")
            
            compra_cog = self.bot.get_cog("CompraCog")
            if compra_cog is None:
                if coins_cog:
                    await coins_cog.adicionar_coins(user_id, preco_item, "Devolução - CompraCog não encontrado")
                
                await interaction.followup.send(
                    "❌ **Erro ao processar compra!**\n"
                    "Por favor, tente novamente ou contate um administrador.",
                    ephemeral=False
                )
                return

            resultado = await compra_cog.processar_compra(interaction, item_id, user_id, item_nome)
            
            if resultado:
                await self.enviar_log_loja(
                    interaction,
                    "Compra Realizada",
                    f"**Item:** {item_nome}\n"
                    f"**Preço:** {preco_item} coins\n"
                    f"**ID do Item:** {item_id}\n"
                    f"**Saldo Anterior:** {saldo_anterior} coins\n"
                    f"**Saldo Atual:** {saldo_atual} coins\n"
                    f"**Diferença:** -{preco_item} coins",
                    discord.Color.green()
                )
                
                await interaction.followup.send(
                    f"✅ **Compra realizada com sucesso!**\n"
                    f"🛒 **{item_nome}**\n"
                    f"💳 **Saldo atual:** {saldo_atual} coins\n",
                    ephemeral=True
                )
            else:
                print(f"❌ COMPRAR: Falha ao processar compra")
                if coins_cog:
                    await coins_cog.adicionar_coins(user_id, preco_item, "Devolução - Falha no processamento")
                else:
                    await interaction.followup.send(
                        "❌ **Erro ao processar sua compra!**\n"
                        "Suas coins foram devolvidas. Por favor, tente novamente.",
                        ephemeral=False
                    )
                    
        except Exception as e:
            print(f"❌ ERRO NO COMANDO COMPRAR: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                coins_cog = self.bot.get_cog("FenrirCoins")
                if coins_cog:
                    await coins_cog.adicionar_coins(user_id, preco_item, "Devolução - Erro no processamento")
                
                await interaction.followup.send(
                    "❌ **Erro ao processar compra!**\n"
                    "Suas coins foram devolvidas. Por favor, tente novamente.",
                    ephemeral=False
                )
            except Exception as followup_error:
                print(f"❌ Erro ao enviar mensagem de erro: {followup_error}")

    @app_commands.command(name="adicionar_item", description="Adicionar um item à loja (ADM)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        nome="Nome do item",
        preco="Preço em coins",
        descricao="Descrição breve do item"
    )
    async def adicionar_item(self, interaction: discord.Interaction, nome: str, preco: int, descricao: str):
        if preco <= 0:
            await interaction.response.send_message("❌ O preço deve ser maior que 0!", ephemeral=True)
            return

        if len(nome) > 50:
            await interaction.response.send_message("❌ O nome do item deve ter no máximo 50 caracteres!", ephemeral=True)
            return

        if len(descricao) > 200:
            await interaction.response.send_message("❌ A descrição deve ter no máximo 200 caracteres!", ephemeral=True)
            return

        novo_item = {
            "id": self.loja_data["proximo_id"],
            "nome": nome,
            "preco": preco,
            "descricao": descricao,
            "criado_por": interaction.user.id,
            "criado_em": time.time()
        }

        self.loja_data["itens"].append(novo_item)
        self.loja_data["proximo_id"] += 1

        self.ordenar_itens()

        embed = discord.Embed(
            title="✅ Item Adicionado à Loja!",
            description=f"**{nome}** foi adicionado com sucesso!\n\n📊 **Itens foram automaticamente ordenados por preço (do mais caro para o mais barato).**",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Preço", value=f"💎 {preco} coins", inline=True)
        embed.add_field(name="📝 ID Interno", value=f"`#{novo_item['id']}`", inline=True)
        embed.add_field(name="📋 Descrição", value=descricao, inline=False)
        
        posicao = self.loja_data["itens"].index(novo_item) + 1
        embed.add_field(name="📍 Posição na Loja", value=f"`#{posicao}` (após ordenação)", inline=False)
        
        embed.set_footer(text="Os usuários já podem comprar este item usando /comprar")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        await self.enviar_log_loja(
            interaction,
            "Item Adicionado",
            f"**Ação:** Adicionou novo item à loja\n"
            f"**Item:** {nome}\n"
            f"**Preço:** {preco} coins\n"
            f"**Descrição:** {descricao}\n"
            f"**ID Interno:** #{novo_item['id']}\n"
            f"**Posição após ordenação:** #{posicao}",
            discord.Color.green()
        )

    @app_commands.command(name="remover_item", description="Remover um item da loja (ADM)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        numero_item="Número do item a ser removido (1, 2, 3...)",
        motivo="Motivo da remoção (opcional)"
    )
    async def remover_item(self, interaction: discord.Interaction, numero_item: int, motivo: str = "Não especificado"):
        item_encontrado = self.encontrar_item_por_posicao(numero_item)
        
        if not item_encontrado:
            await interaction.response.send_message(
                f"❌ Item `#{numero_item}` não encontrado na loja!",
                ephemeral=True
            )
            
            await self.enviar_log_loja(
                interaction,
                "Tentativa de Remoção - Erro",
                f"**Ação:** Tentou remover item #{numero_item}\n**Motivo:** Item não encontrado",
                discord.Color.red()
            )
            return

        for i, item in enumerate(self.loja_data["itens"]):
            if item["id"] == item_encontrado["id"]:
                item_removido = self.loja_data["itens"].pop(i)
                self.salvar_dados()
                break

        embed = discord.Embed(
            title="✅ Item Removido da Loja!",
            description=f"**{item_removido['nome']}** foi removido com sucesso!",
            color=discord.Color.orange()
        )
        embed.add_field(name="💰 Preço Original", value=f"💎 {item_removido['preco']} coins", inline=True)
        embed.add_field(name="📝 Posição Removida", value=f"`#{numero_item}`", inline=True)
        embed.add_field(name="📋 Motivo", value=motivo, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        await self.enviar_log_loja(
            interaction,
            "Item Removido",
            f"**Ação:** Removeu item da loja\n"
            f"**Item:** {item_removido['nome']}\n"
            f"**Preço original:** {item_removido['preco']} coins\n"
            f"**Posição Removida:** #{numero_item}\n"
            f"**Motivo:** {motivo}",
            discord.Color.orange()
        )

    @app_commands.command(name="limpar_loja", description="Remover TODOS os itens da loja (ADM)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        motivo="Motivo da limpeza (opcional)"
    )
    async def limpar_loja(self, interaction: discord.Interaction, motivo: str = "Não especificado"):
        if not self.loja_data["itens"]:
            await interaction.response.send_message("❌ A loja já está vazia!", ephemeral=True)
            return

        quantidade_itens = len(self.loja_data["itens"])
        itens_removidos = self.loja_data["itens"].copy()
        
        self.loja_data["itens"] = []
        self.salvar_dados()

        embed = discord.Embed(
            title="🧹 Loja Limpa!",
            description=f"**{quantidade_itens} itens** foram removidos da loja!",
            color=discord.Color.red()
        )
        embed.add_field(name="📋 Motivo", value=motivo, inline=False)
        
        if quantidade_itens <= 5:
            itens_lista = "\n".join([f"• {item['nome']} (💎 {item['preco']})" for item in itens_removidos])
        else:
            itens_lista = "\n".join([f"• {item['nome']} (💎 {item['preco']})" for item in itens_removidos[:5]]) + f"\n• ... e mais {quantidade_itens - 5} itens"

        embed.add_field(name="🗑️ Itens Removidos", value=itens_lista, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        await self.enviar_log_loja(
            interaction,
            "Loja Limpa",
            f"**Ação:** Limpou toda a loja\n"
            f"**Itens removidos:** {quantidade_itens}\n"
            f"**Motivo:** {motivo}",
            discord.Color.red()
        )

    @adicionar_item.error
    @remover_item.error
    @limpar_loja.error
    async def comandos_adm_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você não tem permissão de administrador para usar este comando.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(LojaCog(bot))