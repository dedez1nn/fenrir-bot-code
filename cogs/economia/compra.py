import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import time

class TituloModal(discord.ui.Modal, title="🏷️ Escolha seu Título Personalizado"):
    def __init__(self, compra_cog, user_id, interaction_original):
        super().__init__()
        self.compra_cog = compra_cog
        self.user_id = user_id
        self.interaction_original = interaction_original
        self.commands_loja = self.compra_cog.bot.get_cog("CommandsLojaCog")
        
        self.titulo_input = discord.ui.TextInput(
            label="Digite seu título personalizado",
            placeholder="Ex: Lenda da Alcateia, Mestre dos Scripts...",
            min_length=3,
            max_length=20,
            required=True
        )
        self.add_item(self.titulo_input)

    async def on_submit(self, interaction: discord.Interaction):
        titulo = self.titulo_input.value.strip()
        
        palavras_proibidas = ["admin", "mod", "staff", "don", "owner", "@", "#", "http", "discord.gg"]
        if any(palavra in titulo.lower() for palavra in palavras_proibidas):
            await interaction.response.send_message(
                "❌ Título contém palavras não permitidas! Escolha outro título.",
                ephemeral=True
            )
            return
        
        xp_cog = self.compra_cog.bot.get_cog("XPCog")
        if xp_cog:
            user_id_str = str(self.user_id)
            if user_id_str in xp_cog.xp_data:
                xp_cog.xp_data[user_id_str]["titulo"] = titulo
                xp_cog.salvar_dados()
        
        await interaction.response.send_message(
            f"✅ **Título Definido com Sucesso!**\n"
            f"Seu novo título é: **{titulo}**\n"
            f"Ele aparecerá no seu perfil do ranking!",
            ephemeral=True
        )
        
        canal_log = self.compra_cog.bot.get_channel(self.compra_cog.bot.config.get("xp_log_channel_id") if self.compra_cog.bot.config else None)
        if canal_log:
            user = self.compra_cog.bot.get_user(self.user_id)
            embed_log = discord.Embed(
                title="🏷️ Título Personalizado Definido",
                description=f"**{user.mention}** definiu seu título para: **{titulo}**",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            embed_log.set_thumbnail(url=user.display_avatar.url)
            await canal_log.send(embed=embed_log)

class CorPremiumModal(discord.ui.Modal, title="🎨 Escolha sua Cor Premium"):
    def __init__(self, compra_cog, user_id, interaction_original):
        super().__init__()
        self.compra_cog = compra_cog
        self.user_id = user_id
        self.interaction_original = interaction_original
        
        self.cor_select = discord.ui.TextInput(
            label="Digite o número da cor desejada (1-4)",
            placeholder="1 - Eco de Baldur 🌌 | 2 - Bruma de Jotunheim 🌫️ | 3 - Brilho de Freyja 💎 | 4 - Luz de Asgard 🌞",
            min_length=1,
            max_length=1,
            required=True
        )
        self.add_item(self.cor_select)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            opcao = int(self.cor_select.value.strip())
            cores_disponiveis = {
                1: {"id": 1428400034952515696, "nome": "🌌・Eco de Baldur", "cor": discord.Color(0xfff4d6)},
                2: {"id": 1428400132272951358, "nome": "🌫️・Bruma de Jotunheim", "cor": discord.Color(0x87afc7)},
                3: {"id": 1428399718945390764, "nome": "💎・Brilho de Freyja", "cor": discord.Color(0xff9ecd)},
                4: {"id": 1428399137057013783, "nome": "🌞 Luz de Asgard", "cor": discord.Color(0xe4e1d9)}
            }
            
            if opcao not in cores_disponiveis:
                await interaction.response.send_message(
                    "❌ Opção inválida! Escolha um número entre 1 e 4.",
                    ephemeral=True
                )
                return
            
            cor_escolhida = cores_disponiveis[opcao]
            guild = interaction.guild
            member = guild.get_member(self.user_id)
            
            if member:
                for cor_id in [cor["id"] for cor in cores_disponiveis.values()]:
                    cargo = guild.get_role(cor_id)
                    if cargo and cargo in member.roles:
                        await member.remove_roles(cargo)
                
                cargo_novo = guild.get_role(cor_escolhida["id"])
                if cargo_novo:
                    await member.add_roles(cargo_novo)
                    asyncio.create_task(self._remover_cor_apos_tempo(member, cargo_novo))

                    await interaction.response.send_message(
                        f"✅ **Cor Premium Ativada!**\n"
                        f"🎨 Você escolheu: **{cor_escolhida['nome']}**\n"
                        f"⏰ Esta cor estará ativa por **1 hora**!",
                        ephemeral=True
                    )
                    
                    canal_log = self.compra_cog.bot.get_channel(self.compra_cog.bot.config.get("xp_log_channel_id") if self.compra_cog.bot.config else None)
                    if canal_log:
                        embed_log = discord.Embed(
                            title="🎨 Cor Premium Selecionada",
                            description=f"**{member.mention}** escolheu a cor: **{cor_escolhida['nome']}**",
                            color=cor_escolhida["cor"],
                            timestamp=discord.utils.utcnow()
                        )
                        embed_log.set_thumbnail(url=member.display_avatar.url)
                        await canal_log.send(embed=embed_log)
                        
                else:
                    await interaction.response.send_message(
                        "❌ Cargo não encontrado! Contate a administração.",
                        ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    "❌ Membro não encontrado no servidor!",
                    ephemeral=True
                )
                
        except ValueError:
            await interaction.response.send_message(
                "❌ Digite apenas números (1, 2, 3 ou 4)!",
                ephemeral=True
            )

    async def _remover_cor_apos_tempo(self, member: discord.Member, cargo: discord.Role):
        await asyncio.sleep(3600)
        try:
            if cargo in member.roles:
                await member.remove_roles(cargo)
        except Exception as e:
            print(f"❌ Erro ao remover cor premium após 1 hora: {e}")

class SelecionarTituloView(discord.ui.View):
    def __init__(self, compra_cog, user_id, interaction_original):
        super().__init__(timeout=300)  
        self.compra_cog = compra_cog
        self.user_id = user_id
        self.interaction_original = interaction_original

    @discord.ui.button(label="🏷️ Escolher Título", style=discord.ButtonStyle.primary, emoji="✏️")
    async def escolher_titulo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Este botão não é para você!",
                ephemeral=True
            )
            return
            
        modal = TituloModal(self.compra_cog, self.user_id, self.interaction_original)
        await interaction.response.send_modal(modal)

class SelecionarCorView(discord.ui.View):
    def __init__(self, compra_cog, user_id, interaction_original):
        super().__init__(timeout=300) 
        self.compra_cog = compra_cog
        self.user_id = user_id
        self.interaction_original = interaction_original

    @discord.ui.button(label="🎨 Escolher Cor", style=discord.ButtonStyle.primary, emoji="🎨")
    async def escolher_cor(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Este botão não é para você!",
                ephemeral=True
            )
            return
            
        modal = CorPremiumModal(self.compra_cog, self.user_id, self.interaction_original)
        await interaction.response.send_modal(modal)

class CompraCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    def get_cooldown_cog(self):
        return self.bot.get_cog("CooldownCog")
    
    def get_coins_cog(self):
        return self.bot.get_cog("FenrirCoins")
          
    async def registrar_cooldown(
        self, user_id: int, item_id: int, cooldown_secs: float | None = None
    ):
        try:
            cooldown_cog = self.get_cooldown_cog()
            if cooldown_cog:
                await cooldown_cog.registrar_compra(user_id, item_id, cooldown_secs=cooldown_secs)
        except Exception as e:
            print(f"❌ Erro ao registrar cooldown: {e}")
            import traceback
            traceback.print_exc()

    async def verificar_cooldown_compra(self, user_id: int, item_id: int) -> bool:
        try:
            cooldown_cog = self.get_cooldown_cog()
            if cooldown_cog:
                return await cooldown_cog.verificar_compra(user_id, item_id)
            return False
        except Exception as e:
            print(f"❌ Erro ao verificar cooldown: {e}")
            return False

    async def enviar_mensagem_ticket(self, interaction: discord.Interaction, item_nome: str):
        _cfg = getattr(interaction.client, "config", None)
        _ch_id = _cfg.get("tickets_channel_id") if _cfg else 0
        mensagem = (
            f"✅ **Compra Confirmada**\n\n"
            f"Para conseguir o **{item_nome}**, abra um ticket em: <#{_ch_id}>\n\n"
            f"📋 **Instruções:**\n"
            f"1. Vá para <#{_ch_id}>\n"
            f"2. Clique em 'Abrir Ticket'\n"
            f"3. Informe que comprou: **{item_nome}**\n"
            f"4. Aguarde a equipe te atender!\n"
            f"⏰ **Tempo de atendimento:** Geralmente em até 24 horas"
        )
        
        if not interaction.response.is_done():
            await interaction.response.send_message(mensagem, ephemeral=True)
        else:
            await interaction.followup.send(mensagem, ephemeral=True)
        
    async def processar_compra(
        self,
        interaction: discord.Interaction,
        item_id: int,
        user_id: int,
        item_nome: str,
        item_db_id: int | None = None,
        cooldown_secs: float | None = None,
    ):
        try:
            print(f"🔍 [DEBUG] Iniciando processar_compra - Item: {item_id}, User: {user_id}")
            # Em DB mode usa o id real do item; em JSON mode usa a posição
            check_id = item_db_id if item_db_id is not None else item_id

            cooldown_ativo = await self.verificar_cooldown_compra(user_id, check_id)
            if cooldown_ativo:
                cooldown_cog = self.get_cooldown_cog()
                if cooldown_cog:
                    tempo_restante = await cooldown_cog.obter_tempo_restante(user_id, check_id)
                    if tempo_restante > 0:
                        dias = int(tempo_restante // 86400)
                        horas = int((tempo_restante % 86400) // 3600)
                        minutos = int((tempo_restante % 3600) // 60)
                        
                        mensagem_cooldown = (
                            f"⏰ **Cooldown ativo!**\n"
                            f"Você já comprou este item recentemente.\n"
                            f"⏳ Tente novamente em **{dias}d {horas}h {minutos}m**"
                        )
                        
                        if not interaction.response.is_done():
                            await interaction.response.send_message(mensagem_cooldown, ephemeral=True)
                        else:
                            await interaction.followup.send(mensagem_cooldown, ephemeral=True)
                        return False

            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=False, thinking=True)
            print("✅ Resposta deferida")
            
            processadores = {
                1: self.processar_nitro,     
                2: self.processar_bot_personalizado, 
                3: self.processar_roubo_coins, 
                4: self.processar_script_personalizado,
                5: self.processar_portao_alcateia, 
                6: self.processar_dobro_experiencia, 
                7: self.processar_titulo_ranking,  
                8: self.processar_cores_premium,    
                9: self.processar_emoji_personalizado,
                10: self.processar_bilheteria,    
                11: self.processar_cor_premium,    
                12: self.processar_enquete,    
                13: self.processar_renomear_canal,
                14: self.processar_fixar_mensagem   
            }
            
            processador = processadores.get(item_id)
            print(f"🔍 [DEBUG] Processador encontrado: {processador}")
            
            if processador:
                print(f"🔍 [DEBUG] Chamando processador para item {item_id}")
                resultado = await processador(interaction, user_id, item_nome, item_id)
                print(f"🔍 [DEBUG] Resultado do processador: {resultado}")
                
                if resultado:
                    print(f"🔍 [DEBUG] Registrando cooldown para user {user_id}, item {check_id}")
                    await self.registrar_cooldown(user_id, check_id, cooldown_secs=cooldown_secs)
                return resultado
            else:
                print(f"🔍 [DEBUG] Nenhum processador encontrado, usando genérico")
                return await self.processar_item_generico(interaction, user_id, item_nome)
                            
        except Exception as e:
            print(f"❌ Erro ao processar compra: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Erro ao processar sua compra. Por favor, abra um ticket para suporte.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ Erro ao processar sua compra. Por favor, abra um ticket para suporte.",
                        ephemeral=True
                    )
            except Exception as followup_error:
                print(f"❌ Erro ao enviar mensagem de erro: {followup_error}")
                
            return False


    async def processar_titulo_ranking(self, interaction: discord.Interaction, user_id: int, item_nome: str, item_id: int):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"✅ **Título Personalizado Comprado!**\n"
                    f"🏷️ Agora você pode escolher seu título personalizado!\n\n"
                    f"**Clique no botão abaixo para definir seu título:**",
                    view=SelecionarTituloView(self, user_id, interaction),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"✅ **Título Personalizado Comprado!**\n"
                    f"🏷️ Agora você pode escolher seu título personalizado!\n\n"
                    f"**Clique no botão abaixo para definir seu título:**",
                    view=SelecionarTituloView(self, user_id, interaction),
                    ephemeral=True
                )
            return True
        except Exception as e:
            print(f"❌ Erro ao processar título ranking: {e}")
            return False

    async def processar_cores_premium(self, interaction: discord.Interaction, user_id: int, item_nome: str, item_id: int):
        MENSAGEM_CORES = (
            f"✅ **Cores PREMIUM Compradas!**\n"
            f"🎨 Agora você tem acesso às cores premium!\n\n"
            f"**Cores disponíveis:**\n"
            f"1️⃣ **Eco de Baldur** 🌌\n"
            f"2️⃣ **Bruma de Jotunheim** 🌫️\n"
            f"3️⃣ **Brilho de Freyja** 💎\n"
            f"4️⃣ **Luz de Asgard** 🌞\n\n"
            f"**Clique no botão abaixo para escolher sua cor:**"
        )
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(MENSAGEM_CORES, view=SelecionarCorView(self, user_id, interaction), ephemeral=True)
            else:
                await interaction.followup.send(MENSAGEM_CORES, view=SelecionarCorView(self, user_id, interaction), ephemeral=True)
            return True
        except Exception as e:
            print(f"❌ Erro ao processar cores premium: {e}")
            return False

    async def processar_cor_premium(self, interaction: discord.Interaction, user_id: int, item_nome: str, item_id: int):
        MENSAGEM_CORES = (
            f"✅ **Cor Premium Comprada!**\n"
            f"✨ Agora você pode escolher uma cor premium por **1 hora**!\n\n"
            f"**Cores disponíveis:**\n"
            f"1️⃣ **Eco de Baldur** 🌌\n"
            f"2️⃣ **Bruma de Jotunheim** 🌫️\n"
            f"3️⃣ **Brilho de Freyja** 💎\n"
            f"4️⃣ **Luz de Asgard** 🌞\n\n"
            f"**Clique no botão abaixo para escolher sua cor:**"
        )
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(MENSAGEM_CORES, view=SelecionarCorView(self, user_id, interaction), ephemeral=True)
            else:
                await interaction.followup.send(MENSAGEM_CORES, view=SelecionarCorView(self, user_id, interaction), ephemeral=True)
            return True
        except Exception as e:
            print(f"❌ Erro ao processar cor premium: {e}")
            return False

    async def processar_nitro(self, interaction: discord.Interaction, user_id: int, item_nome: str, item_id: int):
        try:
            await self.enviar_mensagem_ticket(interaction, item_nome)
            return True
        except Exception as e:
            print(f"❌ Erro ao processar nitro: {e}")
            return False

    async def processar_bot_personalizado(self, interaction: discord.Interaction, user_id: int, item_nome: str, item_id: int):
        try:
            await self.enviar_mensagem_ticket(interaction, item_nome)
            return True
        except Exception as e:
            print(f"❌ Erro ao processar bot personalizado: {e}")
            return False

    async def processar_emoji_personalizado(self, interaction: discord.Interaction, user_id: int, item_nome: str, item_id: int):
        try:
            await self.enviar_mensagem_ticket(interaction, item_nome)
            return True
        except Exception as e:
            print(f"❌ Erro ao processar emoji personalizado: {e}")
            return False

    async def processar_script_personalizado(self, interaction: discord.Interaction, user_id: int, item_nome: str, item_id: int):
        try:
            await self.enviar_mensagem_ticket(interaction, item_nome)
            return True
        except Exception as e:
            print(f"❌ Erro ao processar script personalizado: {e}")
            return False


    async def processar_roubo_coins(self, interaction: discord.Interaction, user_id: int, item_nome: str, item_id: int):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"✅ **Roubo de Coins Ativado!**\n"
                    f"🤫 Agora você pode usar o comando `/roubar`!\n"
                    f"💎 Rouba 40% das coins de um usuário\n"
                    f"⏰ Cooldown: **7 dias por usuário**",
                    ephemeral=False
                )
            else:
                await interaction.followup.send(
                    f"✅ **Roubo de Coins Ativado!**\n"
                    f"🤫 Agora você pode usar o comando `/roubar`!\n"
                    f"💎 Rouba 40% das coins de um usuário\n"
                    f"⏰ Cooldown: **7 dias por usuário**",
                    ephemeral=False
                )
            return True
        except Exception as e:
            print(f"❌ Erro ao processar roubo de coins: {e}")
            return False

    async def processar_dobro_experiencia(self, interaction: discord.Interaction, user_id: int, item_nome: str, item_id: int):
        try:
            xp_cog = self.bot.get_cog("XPCog")
            if xp_cog:
                sucesso = await xp_cog.ativar_dobro_xp(user_id, 12)
                if sucesso:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(
                            f"✅ **Dobro de XP Ativado!**\n"
                            f"🎯 Você ganhará o DOBRO de experiência por **12 horas**!",
                            ephemeral=False
                        )
                    else:
                        await interaction.followup.send(
                            f"✅ **Dobro de XP Ativado!**\n"
                            f"🎯 Você ganhará o DOBRO de experiência por **12 horas**!",
                            ephemeral=False
                        )
                    return True
            
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"✅ **Dobro de XP Ativado!**\n"
                    f"🎯 Você ganhará o DOBRO de experiência por **12 horas**!",
                    ephemeral=False
                )
            else:
                await interaction.followup.send(
                    f"✅ **Dobro de XP Ativado!**\n"
                    f"🎯 Você ganhará o DOBRO de experiência por **12 horas**!",
                    ephemeral=False
                )
            return True
        except Exception as e:
            print(f"❌ Erro ao processar dobro de experiência: {e}")
            return False

    async def processar_bilheteria(self, interaction: discord.Interaction, user_id: int, item_nome: str, item_id: int):
        try:
            coins_ganhos = random.randint(50000, 250000)

            if coins_ganhos > 120000:
                texto = "🎁 **Bilheteria Sortuda!**\n"
                texto_2 = f"🎉 Você ganhou **💎 {coins_ganhos:,} coins**!\n"
            elif coins_ganhos == 120000:
                texto = "😂 **Bilheteria Empatada!**\n"
                texto_2 = f"💎 Você recebeu **{coins_ganhos:,} coins** — sorte mediana!\n"
            else:
                texto = "😢 **Bilheteria Fraca!**\n"
                texto_2 = f"💎 Você recebeu apenas **{coins_ganhos:,} coins**.\n"

            mensagem_final = texto + texto_2 + "💰 Volte em **24 horas** para tentar novamente!"

            coins_cog = self.get_coins_cog()
            if coins_cog:
                await coins_cog.adicionar_coins(user_id, coins_ganhos)

            if not interaction.response.is_done():
                await interaction.response.send_message(mensagem_final, ephemeral=False)
            else:
                await interaction.followup.send(mensagem_final, ephemeral=False)

            return True

        except Exception as e:
            print(f"❌ Erro ao processar bilheteria: {e}")
            return False

    async def processar_renomear_canal(self, interaction: discord.Interaction, user_id: int, item_nome: str, item_id: int):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"✅ **Permissão Concedida!**\n"
                    f"📛 Agora você pode usar `/renomear_canal` para renomear um canal por **1 hora**!\n"
                    f"⏰ Cooldown: **24 horas**",
                    ephemeral=False
                )
            else:
                await interaction.followup.send(
                    f"✅ **Permissão Concedida!**\n"
                    f"📛 Agora você pode usar `/renomear_canal` para renomear um canal por **1 hora**!\n"
                    f"⏰ Cooldown: **24 horas**",
                    ephemeral=False
                )
            return True
        except Exception as e:
            print(f"❌ Erro ao processar renomear canal: {e}")
            return False

    async def processar_portao_alcateia(self, interaction: discord.Interaction, user_id: int, item_nome: str, item_id: int):
        try:
            cargo_portao_id = 1428715049928757318
            guild = interaction.guild
            member = guild.get_member(user_id)
            cargo = guild.get_role(cargo_portao_id)
            
            if cargo and member:
                await member.add_roles(cargo)
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"✅ **Acesso Concedido!**\n"
                        f"🔐 Agora você tem acesso ao **Porão da Alcateia**!\n"
                        f"💻 Scripts não utilizados e reciclados disponíveis\n"
                        f"🌟 Acesso permanente!",
                        ephemeral=False
                    )
                else:
                    await interaction.followup.send(
                        f"✅ **Acesso Concedido!**\n"
                        f"🔐 Agora você tem acesso ao **Porão da Alcateia**!\n"
                        f"💻 Scripts não utilizados e reciclados disponíveis\n"
                        f"🌟 Acesso permanente!",
                        ephemeral=False
                    )
                return True
            else:
                await self.enviar_mensagem_ticket(interaction, item_nome)
                return False
        except Exception as e:
            await self.enviar_mensagem_ticket(interaction, item_nome)
            return False

    async def processar_enquete(self, interaction: discord.Interaction, user_id: int, item_nome: str, item_id: int):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"✅ **Permissão Concedida!**\n"
                    f"📊 Agora você pode usar `/criar_enquete` para criar enquetes **SIM/NÃO**!\n"
                    f"⏰ Cooldown: **12 horas**",
                    ephemeral=False
                )
            else:
                await interaction.followup.send(
                    f"✅ **Permissão Concedida!**\n"
                    f"📊 Agora você pode usar `/criar_enquete` para criar enquetes **SIM/NÃO**!\n"
                    f"⏰ Cooldown: **12 horas**",
                    ephemeral=False
                )
            return True
        except Exception as e:
            print(f"❌ Erro ao processar enquete: {e}")
            return False

    async def processar_fixar_mensagem(self, interaction: discord.Interaction, user_id: int, item_nome: str, item_id: int):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"✅ **Permissão Concedida!**\n"
                    f"📌 Agora você pode usar `/fixar_mensagem` para fixar uma mensagem por **1 hora**!\n"
                    f"⏰ Cooldown: **6 horas**",
                    ephemeral=False
                )
            else:
                await interaction.followup.send(
                    f"✅ **Permissão Concedida!**\n"
                    f"📌 Agora você pode usar `/fixar_mensagem` para fixar uma mensagem por **1 hora**!\n"
                    f"⏰ Cooldown: **6 horas**",
                    ephemeral=False
                )
            return True
        except Exception as e:
            print(f"❌ Erro ao processar fixar mensagem: {e}")
            return False

    async def processar_item_generico(self, interaction: discord.Interaction, item_nome: str):
        try:
            await self.enviar_mensagem_ticket(interaction, item_nome)
            return True
        except Exception as e:
            print(f"❌ Erro ao processar item genérico: {e}")
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(CompraCog(bot))