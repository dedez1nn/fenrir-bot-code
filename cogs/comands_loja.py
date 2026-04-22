import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import time

class ComandosLojaCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cooldowns = {}

    def get_cooldown_cog(self):
        return self.bot.get_cog("CooldownCog")

    async def verificar_compra(self, user_id: int, item_id: int) -> bool:
        cooldown_cog = self.get_cooldown_cog()
        if cooldown_cog:
            return cooldown_cog.verificar_compra(user_id, item_id)
        return False

    async def verificar_cooldown(self, user_id: int, comando: str, cooldown_segundos: int) -> bool:
        agora = time.time()
        chave = f"{user_id}_{comando}"
        
        if chave in self.cooldowns:
            tempo_restante = self.cooldowns[chave] - agora
            if tempo_restante > 0:
                return tempo_restante
        
        self.cooldowns[chave] = agora + cooldown_segundos
        return 0

    @app_commands.command(name="roubar", description="🎭 Rouba 40% das coins de um usuário (Requer compra)")
    async def roubar(self, interaction: discord.Interaction, vitima: discord.Member):
        
        if interaction.channel.id != 1426205118293868748:
            await interaction.response.send_message(f"❌ Ei, {interaction.user.mention}, use esse **comando** apenas em {self.bot.get_channel(1426205118293868748).mention} !", ephemeral=True)
            return
        
        try:
            if not await self.verificar_compra(interaction.user.id, 3):
                await interaction.response.send_message(
                    "❌ **Você precisa comprar o item 'Roubo de Coins' na loja para usar este comando!**\n"
                    "💎 Use `/loja` para ver os itens disponíveis.",
                    ephemeral=True
                )
                return

            cooldown_vitima = await self.verificar_cooldown(
                interaction.user.id, 
                f"roubar_{vitima.id}", 
                604800 
            )
            
            if cooldown_vitima > 0:
                dias = int(cooldown_vitima // 86400)
                horas = int((cooldown_vitima % 86400) // 3600)
                await interaction.response.send_message(
                    f"⏰ **Cooldown ativo!**\n"
                    f"Você só pode roubar {vitima.mention} novamente em **{dias}d {horas}h**!",
                    ephemeral=True
                )
                return

            if vitima.id == interaction.user.id:
                await interaction.response.send_message(
                    "🤨 **Você não pode roubar a si mesmo!**",
                    ephemeral=True
                )
                return

            if vitima.bot:
                await interaction.response.send_message(
                    "🤖 **Bots não possuem coins para roubar!**",
                    ephemeral=True
                )
                return

            coins_cog = self.bot.get_cog("FenrirCoins")
            if not coins_cog:
                await interaction.response.send_message(
                    "❌ **Sistema de coins indisponível no momento.**",
                    ephemeral=True
                )
                return

            coins_vitima = await coins_cog.obter_coins(vitima.id)
            if coins_vitima < 100: 
                await interaction.response.send_message(
                    f"💸 **{vitima.display_name} não tem coins suficientes para roubar!**\n"
                    f"É necessário ter pelo menos **100 coins**.",
                    ephemeral=True
                )
                return

            coins_roubadas = int(coins_vitima * 0.4)
            
            sucesso = random.random() < 0.7

            if sucesso:
                await coins_cog.remover_coins(vitima.id, coins_roubadas, f"Roubado por {interaction.user}")
                await coins_cog.adicionar_coins(interaction.user.id, coins_roubadas, f"Roubo de {vitima}")

                embed = discord.Embed(
                    title="🎭 Roubo Bem Sucedido!",
                    description=(
                        f"**{interaction.user.mention}** roubou **{vitima.mention}** com sucesso!\n\n"
                        f"💎 **Coins roubadas:** `{coins_roubadas:,}`\n"
                        f"👤 **Vitima perdeu:** `{coins_roubadas:,}` coins\n"
                        f"🤑 **Ladrão ganhou:** `{coins_roubadas:,}` coins\n"
                        f"⏰ **Cooldown:** 7 dias para esta vítima"
                    ),
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                
                canal_log = self.bot.get_channel(1427479688544129064)
                if canal_log:
                    embed_log = discord.Embed(
                        title="🎭 Roubo de Coins Executado",
                        description=(
                            f"**Ladrão:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                            f"**Vítima:** {vitima.mention} (`{vitima.id}`)\n"
                            f"**Coins roubadas:** `{coins_roubadas:,}`\n"
                            f"**Saldo anterior da vítima:** `{coins_vitima:,}`"
                        ),
                        color=discord.Color.orange(),
                        timestamp=discord.utils.utcnow()
                    )
                    await canal_log.send(embed=embed_log)

            else:
                coins_ladrao = await coins_cog.obter_coins(interaction.user.id)
                multa = min(int(coins_ladrao * 0.1), 1000) 
                
                if multa > 0:
                    await coins_cog.remover_coins(interaction.user.id, multa, "Multa por roubo falhado")
                    await coins_cog.adicionar_coins(vitima.id, multa, "Compensação por tentativa de roubo")

                embed = discord.Embed(
                    title="🚨 Roubo Falhou!",
                    description=(
                        f"**{interaction.user.mention}** tentou roubar **{vitima.mention}** mas foi pego!\n\n"
                        f"💰 **Multa aplicada:** `{multa:,}` coins\n"
                        f"🛡️ **Vítima compensada:** `{multa:,}` coins\n"
                        f"⏰ **Cooldown:** 7 dias para esta vítima\n\n"
                        f"*Melhor sorte na próxima vez!*"
                    ),
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            print(f"❌ Erro no comando roubar: {e}")
            await interaction.response.send_message(
                "❌ **Erro ao executar o roubo. Tente novamente mais tarde.**",
                ephemeral=True
            )

    @app_commands.command(name="renomear_canal", description="📛 Renomeia um canal por 1 hora (Requer compra)")
    @app_commands.describe(
        canal="Canal a ser renomeado",
        novo_nome="Novo nome do canal (máx. 25 caracteres)"
    )
    async def renomear_canal(self, interaction: discord.Interaction, canal: discord.TextChannel, novo_nome: str):
        
        if interaction.channel.id != 1426205118293868748:
            await interaction.response.send_message(f"❌ Ei, {interaction.user.mention}, use esse **comando** apenas em {self.bot.get_channel(1426205118293868748).mention} !", ephemeral=True)
            return
        
        try:
            if not await self.verificar_compra(interaction.user.id, 13):
                await interaction.response.send_message(
                    "❌ **Você precisa comprar o item 'Renomear Canal' na loja para usar este comando!**",
                    ephemeral=True
                )
                return

            cooldown_restante = await self.verificar_cooldown(interaction.user.id, "renomear_canal", 86400)
            if cooldown_restante > 0:
                horas = int(cooldown_restante // 3600)
                minutos = int((cooldown_restante % 3600) // 60)
                await interaction.response.send_message(
                    f"⏰ **Cooldown ativo!**\n"
                    f"Você pode usar este comando novamente em **{horas}h {minutos}m**!",
                    ephemeral=True
                )
                return

            if len(novo_nome) < 2 or len(novo_nome) > 25:
                await interaction.response.send_message(
                    "❌ **O nome do canal deve ter entre 2 e 25 caracteres!**",
                    ephemeral=True
                )
                return

            if not canal.permissions_for(interaction.guild.me).manage_channels:
                await interaction.response.send_message(
                    "❌ **Não tenho permissão para gerenciar canais!**",
                    ephemeral=True
                )
                return

            nome_original = canal.name
            
            await canal.edit(name=novo_nome[:25])

            embed = discord.Embed(
                title="📛 Canal Renomeado!",
                description=(
                    f"**Canal renomeado com sucesso!**\n\n"
                    f"**Canal:** {canal.mention}\n"
                    f"**Nome original:** `{nome_original}`\n"
                    f"**Novo nome:** `{novo_nome}`\n"
                    f"**Duração:** 1 hora\n"
                    f"**Renomeado por:** {interaction.user.mention}"
                ),
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )

            await interaction.response.send_message(embed=embed)

            canal_log = self.bot.get_channel(1427479688544129064)
            if canal_log:
                embed_log = discord.Embed(
                    title="📛 Canal Renomeado Temporariamente",
                    description=(
                        f"**Usuário:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                        f"**Canal:** {canal.mention} (`{canal.id}`)\n"
                        f"**De:** `{nome_original}`\n"
                        f"**Para:** `{novo_nome}`\n"
                        f"**Duração:** 1 hora"
                    ),
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                await canal_log.send(embed=embed_log)

            await asyncio.sleep(3600) 
            try:
                await canal.edit(name=nome_original)
      
                embed_restaurado = discord.Embed(
                    title="🔄 Nome Restaurado",
                    description=f"O canal voltou ao nome original: `{nome_original}`",
                    color=discord.Color.green()
                )
                await canal.send(embed=embed_restaurado)
                
            except Exception as e:
                print(f"❌ Erro ao restaurar nome do canal: {e}")

        except Exception as e:
            print(f"❌ Erro no comando renomear_canal: {e}")
            await interaction.response.send_message(
                "❌ **Erro ao renomear o canal. Verifique minhas permissões.**",
                ephemeral=True
            )

    @app_commands.command(name="criar_enquete", description="📊 Cria uma enquete SIM/NÃO (Requer compra)")
    @app_commands.describe(
        pergunta="Pergunta para a enquete",
        duracao_minutos="Duração da enquete em minutos (padrão: 60)"
    )
    async def criar_enquete(self, interaction: discord.Interaction, pergunta: str, duracao_minutos: int = 60):
        
        if interaction.channel.id != 1426205118293868748:
            await interaction.response.send_message(f"❌ Ei, {interaction.user.mention}, use esse **comando** apenas em {self.bot.get_channel(1426205118293868748).mention} !", ephemeral=True)
            return
        
        try:
            if not await self.verificar_compra(interaction.user.id, 12):
                await interaction.response.send_message(
                    "❌ **Você precisa comprar o item 'Enquete' na loja para usar este comando!**",
                    ephemeral=True
                )
                return

            cooldown_restante = await self.verificar_cooldown(interaction.user.id, "criar_enquete", 43200)
            if cooldown_restante > 0:
                horas = int(cooldown_restante // 3600)
                minutos = int((cooldown_restante % 3600) // 60)
                await interaction.response.send_message(
                    f"⏰ **Cooldown ativo!**\n"
                    f"Você pode criar outra enquete em **{horas}h {minutos}m**!",
                    ephemeral=True
                )
                return

            if duracao_minutos < 1 or duracao_minutos > 1440: 
                await interaction.response.send_message(
                    "❌ **A duração deve ser entre 1 minuto e 24 horas (1440 minutos)!**",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="📊 Enquete",
                description=pergunta,
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_author(name=f"Enquete de {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
            embed.set_footer(text=f"Enquete termina em {duracao_minutos} minutos")

            mensagem = await interaction.channel.send(embed=embed)
            await mensagem.add_reaction("✅") 
            await mensagem.add_reaction("❌") 

            await interaction.response.send_message(
                f"✅ **Enquete criada com sucesso!**\n"
                f"📊 Acesse: {mensagem.jump_url}",
                ephemeral=True
            )

            canal_log = self.bot.get_channel(1427479688544129064)
            if canal_log:
                embed_log = discord.Embed(
                    title="📊 Enquete Criada",
                    description=(
                        f"**Criador:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                        f"**Pergunta:** {pergunta}\n"
                        f"**Duração:** {duracao_minutos} minutos\n"
                        f"**Canal:** {interaction.channel.mention}"
                    ),
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                await canal_log.send(embed=embed_log)

        except Exception as e:
            print(f"❌ Erro no comando criar_enquete: {e}")
            await interaction.response.send_message(
                "❌ **Erro ao criar a enquete. Tente novamente.**",
                ephemeral=True
            )

    @app_commands.command(name="fixar_mensagem", description="📌 Fixa uma mensagem por 1 hora (Requer compra)")
    @app_commands.describe(mensagem_id="ID da mensagem para fixar")
    async def fixar_mensagem(self, interaction: discord.Interaction, mensagem_id: str):
        
        if interaction.channel.id != 1426205118293868748:
            await interaction.response.send_message(f"❌ Ei, {interaction.user.mention}, use esse **comando** apenas em {self.bot.get_channel(1426205118293868748).mention} !", ephemeral=True)
            return
        
        try:
            if not await self.verificar_compra(interaction.user.id, 14):
                await interaction.response.send_message(
                    "❌ **Você precisa comprar o item 'Fixar Mensagem' na loja para usar este comando!**",
                    ephemeral=True
                )
                return

            cooldown_restante = await self.verificar_cooldown(interaction.user.id, "fixar_mensagem", 21600)
            if cooldown_restante > 0:
                horas = int(cooldown_restante // 3600)
                minutos = int((cooldown_restante % 3600) // 60)
                await interaction.response.send_message(
                    f"⏰ **Cooldown ativo!**\n"
                    f"Você pode fixar outra mensagem em **{horas}h {minutos}m**!",
                    ephemeral=True
                )
                return

            try:
                mensagem = await interaction.channel.fetch_message(int(mensagem_id))
            except:
                await interaction.response.send_message(
                    "❌ **Mensagem não encontrada! Certifique-se de que o ID está correto.**",
                    ephemeral=True
                )
                return

            if mensagem.pinned:
                await interaction.response.send_message(
                    "❌ **Esta mensagem já está fixada!**",
                    ephemeral=True
                )
                return

            await mensagem.pin()

            embed = discord.Embed(
                title="📌 Mensagem Fixada!",
                description=(
                    f"**Mensagem fixada com sucesso!**\n\n"
                    f"**Autor:** {mensagem.author.mention}\n"
                    f"**Conteúdo:** {mensagem.content[:100]}{'...' if len(mensagem.content) > 100 else ''}\n"
                    f"**Duração:** 1 hora\n"
                    f"**Fixado por:** {interaction.user.mention}"
                ),
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

            await asyncio.sleep(3600)
            try:
                await mensagem.unpin()
                await interaction.channel.send(
                    f"📌 Mensagem de {mensagem.author.mention} foi desfixada automaticamente."
                )
            except Exception as e:
                print(f"❌ Erro ao desfixar mensagem: {e}")

        except Exception as e:
            print(f"❌ Erro no comando fixar_mensagem: {e}")
            await interaction.response.send_message(
                "❌ **Erro ao fixar a mensagem. Verifique minhas permissões.**",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(ComandosLojaCog(bot))