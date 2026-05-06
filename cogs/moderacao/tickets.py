import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import datetime
import os

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎫 Suporte", style=discord.ButtonStyle.blurple, custom_id="abrir_suporte")
    async def suporte(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.criar_ticket(interaction, "suporte")
    
    @discord.ui.button(label="💰 Doação", style=discord.ButtonStyle.green, custom_id="abrir_doacao")
    async def doacao(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.criar_ticket(interaction, "doacao")
    
    async def criar_ticket(self, interaction: discord.Interaction, tipo: str):
        try:
            await interaction.response.defer(ephemeral=True)
            
            servidor = interaction.guild
            usuario = interaction.user
            
            categorias = {
                "suporte": 1426304224429608990,
                "doacao": 1426306944204804146
            }
            
            if tipo not in categorias or not categorias[tipo]:
                await interaction.followup.send("❌ Categoria não configurada para este tipo de ticket!", ephemeral=True)
                return
            
            categoria = discord.utils.get(servidor.categories, id=categorias[tipo])
            if not categoria:
                await interaction.followup.send("❌ Categoria não encontrada!", ephemeral=True)
                return
            
            # Verificar tickets existentes do usuário
            for canal in categoria.channels:
                if f"{tipo}-{usuario.name}".lower() in canal.name.lower():
                    await interaction.followup.send(f"❌ Você já tem um ticket de {tipo} aberto: {canal.mention}", ephemeral=True)
                    return
            
            nome_canal = f"{tipo}-{usuario.name}"
            
            id_fundador = 1426202850769244301
            id_developer = 1426203167049121894
            
            cargo_fundador = servidor.get_role(id_fundador)
            cargo_developer = servidor.get_role(id_developer)
            
            overwrites = {
                servidor.default_role: discord.PermissionOverwrite(view_channel=False),
                
                usuario: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True
                ),
                
                servidor.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    read_message_history=True,
                    manage_channels=True
                )
            }

            if cargo_fundador:
                overwrites[cargo_fundador] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    read_message_history=True,
                    manage_channels=True
                )

            if cargo_developer:
                overwrites[cargo_developer] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    read_message_history=True,
                    manage_channels=True
                )

            novo_canal = await categoria.create_text_channel(
                name=nome_canal,
                overwrites=overwrites,
                reason=f"Ticket de {tipo} aberto por {usuario}"
            )
            
            embed = discord.Embed(
                title=f"🎫 Ticket de {tipo.title()}",
                description=f"Olá {usuario.mention}!\n\n"
                          f"• **Tipo:** {tipo.title()}\n"
                          f"• **Aberto por:** {usuario.display_name}\n"
                          f"• **Data:** {discord.utils.format_dt(discord.utils.utcnow(), 'F')}\n\n"
                          f"A equipe de suporte será notificada e estará com você em breve.\n"
                          f"Enquanto isso, descreva seu problema ou solicitação.",
                color=discord.Color.blue() if tipo == "suporte" else discord.Color.green()
            )
            
            view = discord.ui.View()
            view.add_item(FecharTicketButton())
            
            mensagem = await novo_canal.send(embed=embed, view=view)
            
            await interaction.followup.send(f"✅ Ticket criado com sucesso: {novo_canal.mention}", ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Erro ao criar ticket: {str(e)}", ephemeral=True)

class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    async def ticket(self, canal: discord.TextChannel):
        try:
            embed = discord.Embed(
                title="🎫 Sistema de Tickets",
                description=(
                    "**Selecione o tipo de ticket que deseja abrir:**\n\n"
                    "• 🎫 **Suporte**: Para suporte técnico e dúvidas sobre nossas competências de desenvolvimento dos bots e funcionamento do servidor.\n"
                    "• 💰 **Doação**: Para assuntos pendentes com Planos Premium, fechar parceria, ou oferecer prêmios para Eventos/Sorteios!!\n\n"
                    "Clique em um dos botões abaixo para abrir seu ticket!"
                ),
                color=discord.Color.blue()
            )

            embed.set_footer(text="Fenrir BOT")
            embed.set_thumbnail(
                url="https://cdn.discordapp.com/attachments/1156734159457353848/1426287031922720868/Design_sem_nome_15.png?ex=68eaaccf&is=68e95b4f&hm=8dcb75de780ad5d8955bcd22d8c12bce3e8c5c92f2f18b6dae5006576f869e6a&"
            )
            embed.set_image(
                url="https://cdn.discordapp.com/attachments/1156734159457353848/1426321610763141200/SEJA_BEM-VINDO.gif?ex=68eacd03&is=68e97b83&hm=7326b00835527cee66ed0c996ecf9a14a0dafab10aa5a283463a1dfcfa587a04&"
            )

            view = TicketView()

            await canal.send(embed=embed, view=view)
            print(f"✅ Embed de ticket configurada em #{canal.name}")

        except Exception as e:
            print(f"❌ Erro ao configurar embed de ticket: {e}")

    async def criar_transcript(self, canal: discord.TextChannel) -> str:
        try:
            criado_em = canal.created_at.strftime("%d/%m/%Y às %H:%M:%S")
            total_mensagens = 0
            mensagens_formatadas = []
            
            async for mensagem in canal.history(limit=None, oldest_first=True):
                total_mensagens += 1
                
                timestamp = mensagem.created_at.strftime("%d/%m/%Y %H:%M:%S")
                
                autor = f"{mensagem.author.display_name} ({mensagem.author.id})"
                if mensagem.author.bot:
                    autor += " 🤖"
                
                conteudo = mensagem.clean_content
                if not conteudo.strip():
                    conteudo = "*[Mensagem vazia]*"
                
                anexos_info = ""
                if mensagem.attachments:
                    anexos_nomes = [f"`{att.filename}`" for att in mensagem.attachments]
                    anexos_info = f"\n    📎 Anexos: {', '.join(anexos_nomes)}"
                
                embeds_info = ""
                if mensagem.embeds:
                    embeds_info = f"\n    📊 Embeds: {len(mensagem.embeds)}"
                
                stickers_info = ""
                if mensagem.stickers:
                    stickers_info = f"\n    🎨 Stickers: {len(mensagem.stickers)}"
                
                linha = f"┌─ [{timestamp}] {autor}\n"
                linha += f"│ {conteudo}"
                if anexos_info:
                    linha += anexos_info
                if embeds_info:
                    linha += embeds_info
                if stickers_info:
                    linha += stickers_info
                linha += f"\n└─────\n"
                
                mensagens_formatadas.append(linha)
            
            conteudo_transcript = "╔══════════════════════════════════════════════════╗\n"
            conteudo_transcript += "║                 TRANSCRIPT DO TICKET               ║\n"
            conteudo_transcript += "╠══════════════════════════════════════════════════╣\n"
            conteudo_transcript += f"║ Canal: {canal.name:<35} ║\n"
            conteudo_transcript += f"║ Criado em: {criado_em:<25} ║\n"
            conteudo_transcript += f"║ Total de mensagens: {total_mensagens:<16} ║\n"
            conteudo_transcript += f"║ Gerado em: {datetime.datetime.now().strftime('%d/%m/%Y às %H:%M:%S'):<22} ║\n"
            conteudo_transcript += "╠══════════════════════════════════════════════════╣\n"
            conteudo_transcript += "║                   HISTÓRICO                       ║\n"
            conteudo_transcript += "╚══════════════════════════════════════════════════╝\n\n"
            
            if mensagens_formatadas:
                conteudo_transcript += "\n".join(mensagens_formatadas)
            else:
                conteudo_transcript += "Nenhuma mensagem encontrada neste ticket.\n"
            
            conteudo_transcript += "\n" + "═" * 60 + "\n"
            conteudo_transcript += "📋 Transcript gerado automaticamente pelo sistema de tickets\n"
            conteudo_transcript += f"⚙️  Gerado por: {self.bot.user.display_name}\n"
            
            return conteudo_transcript
            
        except Exception as e:
            print(f"Erro ao criar transcript: {e}")
            return None

    async def enviar_transcript_privado(self, usuario: discord.Member, transcript: str, nome_canal: str):
        nome_arquivo = f"transcript_{nome_canal}.txt"
        try:
            with open(nome_arquivo, "w", encoding="utf-8") as f:
                f.write(transcript)
            
            embed = discord.Embed(
                title="📄 Transcript do Ticket",
                description=f"Aqui está o transcript do seu ticket **{nome_canal}**.\n\n"
                          f"**Informações:**\n"
                          f"• 📁 Arquivo anexado com histórico completo\n"
                          f"• 📊 Formato organizado e legível\n"
                          f"• 💾 Salve para seus registros",
                color=discord.Color.blue()
            )
            
            embed.set_footer(text="Obrigado por utilizar nosso sistema de tickets!")
            
            await usuario.send(embed=embed, file=discord.File(nome_arquivo))
            
            return True
            
        except discord.Forbidden:
            print(f"Não foi possível enviar DM para {usuario.name}")
            return False
        except Exception as e:
            print(f"Erro ao enviar transcript: {e}")
            return False
        finally:
            if os.path.exists(nome_arquivo):
                os.remove(nome_arquivo)

    async def enviar_transcript_canal_logs(self, canal_ticket: discord.TextChannel, transcript: str, usuario_fechou: discord.Member, usuario_abriu: discord.Member):
        nome_arquivo = f"transcript_{canal_ticket.name}.txt"
        try:
            canal_logs_id = 1426323866963410985
            canal_logs = canal_ticket.guild.get_channel(canal_logs_id)
            
            if not canal_logs:
                print("Canal de logs não encontrado!")
                return False

            with open(nome_arquivo, "w", encoding="utf-8") as f:
                f.write(transcript)

            embed_logs = discord.Embed(
                title="🔒 Ticket Fechado",
                description=f"**Ticket:** `{canal_ticket.name}`\n"
                          f"**Aberto por:** {usuario_abriu.mention} (`{usuario_abriu.id}`)\n"
                          f"**Fechado por:** {usuario_fechou.mention} (`{usuario_fechou.id}`)\n"
                          f"**Data:** {discord.utils.format_dt(discord.utils.utcnow(), 'F')}\n"
                          f"**Criado em:** {discord.utils.format_dt(canal_ticket.created_at, 'F')}",
                color=discord.Color.red()
            )
            
            embed_logs.set_footer(text=f"Ticket fechado • {self.bot.user.display_name}")
            
            await canal_logs.send(embed=embed_logs, file=discord.File(nome_arquivo))
            
            return True
            
        except Exception as e:
            print(f"Erro ao enviar para canal de logs: {e}")
            return False
        finally:
            if os.path.exists(nome_arquivo):
                os.remove(nome_arquivo)

class FecharTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="🔒 Fechar Ticket",
            style=discord.ButtonStyle.danger,
            custom_id="fechar_ticket"
        )
    
    async def callback(self, interaction: discord.Interaction):
        try:
            canal = interaction.channel
            
            id_fundador = 1426202850769244301
            id_developer = 1426203167049121894
            
            tem_permissao = False
            
            usuario_ticket = None
            for member in interaction.guild.members:
                if f"-{member.name}" in canal.name or f"-{member.display_name}" in canal.name:
                    usuario_ticket = member
                    break
            
            if usuario_ticket and usuario_ticket.id == interaction.user.id:
                tem_permissao = True
            
            if any(role.id == id_fundador for role in interaction.user.roles):
                tem_permissao = True
            
            if any(role.id == id_developer for role in interaction.user.roles):
                tem_permissao = True
            
            if interaction.user.guild_permissions.administrator:
                tem_permissao = True
            
            if not tem_permissao:
                await interaction.response.send_message(
                    "❌ Apenas quem abriu o ticket, FUNDADOR ou Developer podem fechá-lo!", 
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="🔒 Fechar Ticket",
                description="Tem certeza que deseja fechar este ticket?",
                color=discord.Color.orange()
            )
            
            view = discord.ui.View()
            view.add_item(ConfirmarFecharButton())
            view.add_item(CancelarFecharButton())
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro: {str(e)}", ephemeral=True)

class ConfirmarFecharButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="✅ Confirmar",
            style=discord.ButtonStyle.danger,
            custom_id="confirmar_fechar"
        )
    
    async def callback(self, interaction: discord.Interaction):
        try:
            canal = interaction.channel
            
            usuario_ticket = None
            for member in interaction.guild.members:
                if f"-{member.name}" in canal.name or f"-{member.display_name}" in canal.name:
                    usuario_ticket = member
                    break
            
            cog = interaction.client.get_cog('TicketCog')
            transcript = await cog.criar_transcript(canal)
            
            embed_fechado = discord.Embed(
                title="🔒 Ticket Fechado",
                description=f"**O canal será fechado em 3 segundos**\n\n"
                          f"• **Fechado por:** {interaction.user.mention}\n"
                          f"• **Data:** {discord.utils.format_dt(discord.utils.utcnow(), 'F')}\n\n"
                          f"*O transcript será enviado via mensagem privada e para o canal de logs.*",
                color=discord.Color.red()
            )
            
            await interaction.response.edit_message(content="", embed=embed_fechado, view=None)
            
            await asyncio.sleep(3)
            
            if transcript and usuario_ticket:
                await cog.enviar_transcript_privado(usuario_ticket, transcript, canal.name)
            
            if transcript and usuario_ticket:
                await cog.enviar_transcript_canal_logs(canal, transcript, interaction.user, usuario_ticket)
            
            await canal.delete(reason=f"Ticket fechado por {interaction.user}")
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao fechar ticket: {str(e)}", ephemeral=True)

class CancelarFecharButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="❌ Cancelar",
            style=discord.ButtonStyle.secondary,
            custom_id="cancelar_fechar"
        )
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="✅ Ação cancelada.", embed=None, view=None)

async def setup(bot):
    await bot.add_cog(TicketCog(bot))