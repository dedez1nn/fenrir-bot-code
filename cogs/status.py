import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime


class StatusCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.status_canal = 1427311999381147708

    async def status(self, canal):
        if canal is None and hasattr(self, 'status_canal'):
            canal = self.bot.get_channel(self.status_canal)
        
        canal_changelog = self.bot.get_channel(1427311999381147708)
        embed = discord.Embed(
            title="🤖 Status do Bot",
            description="Olá, pessoal! Estou **on-line**, interagindo\n"
                        "com vocês e de olho nos próximos passos! 🎉\n"
                        f"confira as minhas alterações em {canal_changelog.mention if canal_changelog else 'canal não encontrado'}",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        agora = int(datetime.now().timestamp())
        embed.add_field(name="⚙️ Versão:", value="`2.0.0`", inline=True)
        embed.add_field(name="🔌 Status:", value="`On-line`", inline=False)
        embed.add_field(name="⌛ Latência:", value=f"`{round(self.bot.latency * 1000)}ms`", inline=False)
        embed.add_field(name="🖥️ Programador Responsável:", value="`dedez1n1`", inline=False)
        embed.add_field(name="🕰️ Última vez off-line:", value=f"<t:{agora}:R>", inline=True)

        if self.bot.user.display_avatar:
            embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)
        else:
            embed.set_author(name=self.bot.user.name)

        embed.set_footer(text="© 2025 ALCATEIA DO FENRIR. Todos os direitos reservados.")

        await canal.send(embed=embed)
        
    @app_commands.command(name="manutencao", description="Envia mensagem de reinício (DEVS).")
    async def reiniciando(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Apenas administradores podem usar este comando!", ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🤖 Status do Bot",
            description="Olá, pessoal! Estarei **off-line** nos próximos minutos\n"
                        "enquanto isso, deem uma relaxada, porque jajá estou 🎉\n"
                        f"de volta! Informarei assim que estiver **on-line**.\n\n"
                        "**Motivo**: Manutenção.",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        agora = int(datetime.now().timestamp())
        embed.add_field(name="⚙️ Versão:", value="`2.0.0`", inline=True)
        embed.add_field(name="🔌 Status:", value="`Off-line`", inline=False)
        embed.add_field(name="🖥️ Programador Responsável:", value="`dedez1n1`", inline=False)
        embed.add_field(name="🕰️ Última vez on-line:", value=f"<t:{agora}:R>", inline=True)

        if self.bot.user.display_avatar:
            embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)
        else:
            embed.set_author(name=self.bot.user.name)
            
        embed.set_footer(text="© 2025 ALCATEIA DO FENRIR. Todos os direitos reservados.")

        await interaction.response.send_message(embed=embed)
        
    @commands.command(name="changelog")
    async def changelog(self, ctx):
        embed_coins = discord.Embed(
            title="🏦 SISTEMA DE COINS E ECONOMIA",
            description=(
                "Acumule riquezas e compre vantagens exclusivas!\n\n"
                "**Comandos disponíveis:**\n"
                "`/coins [membro]` — Consulta saldo de coins\n"
                "`/daily` — Resgate coins diárias\n"
                "`/transferir <membro> <quantia>` — Transfira coins\n"
                "`/ranking_coins` — Ranking dos mais ricos!\n\n"
                "**💎 Ganhando Coins**\n"
                "• Mensagens: **+2.500 coins** a cada 3 minutos\n"
                "• Tempo em voz: **+7.500 coins** a cada 5 minutos\n"
                "• Daily: **+10.000 coins** + bônus de streak!\n"
                "• Vitórias: **+20.000 coins** por vitória\n\n"
                "🎯 Valores Reais do Sistema:\n"
                "- Mensagens: Ganhe Coins e XP ao enviar mensagens!\n"
                "- Voz: Ganhe Coins e XP por tempo em voz!\n"
                "- Daily: 10.000 coins + 15.000 por streak\n"
                "- Bônus Level Up: Coins extras a cada 5 níveis\n\n"
                "🛒 Onde Usar?\n"
                "• Loja do servidor\n• Itens especiais\n• Vantagens exclusivas\n• Sistema de apostas\n\n"
                "🔥 Bônus de Streak Diário\n"
                "Base: 10.000 coins\n+15.000 coins por dia de streak\nMultiplicadores premium aplicados!\n\n"
                "*Acumule fortuna e torne-se uma lenda! 💰*"
            ),
            color=0xFFD700
        )
        await ctx.send(embed=embed_coins)

        embed_premium = discord.Embed(
            title="🌟 SISTEMA PREMIUM - VANTAGENS EXCLUSIVAS",
            description=(
                "Eleve sua experiência com nossos planos especiais!\n\n"
                "**Comandos disponíveis:**\n"
                "`/premium` — Veja os planos disponíveis\n"
                "`/premium_status` — Seu status premium\n\n"
                "🟢 Plano Aventureiro (50.000 coins)\n"
                "• 2x XP em todas atividades\n• 2x Coins em mensagens/voz\n• Limite de 10 membros na guild\n• 2 administradores na guild\n\n"
                "🟠 Plano Lendário (150.000 coins)\n"
                "• 4x XP e 4x Coins\n• Limite de 20 membros na guild\n• 3 administradores\n• +20% XP para toda a guild\n\n"
                "🟣 Plano Mítico (300.000 coins)\n"
                "• 6x XP e 6x Coins\n• Limite de 50 membros na guild\n• 5 administradores\n• +50% XP para guild\n• Farm AFK ativado\n\n"
                "🚀 Benefícios Gerais\n"
                "• Multiplicadores de XP/Coins\n• Limites expandidos de guild\n• Bônus para membros da guild\n• Recursos exclusivos\n• Suporte prioritário\n\n"
                "*Torne-se lendário com vantagens exclusivas! 💫*"
            ),
            color=0x8A2BE2
        )
        await ctx.send(embed=embed_premium)

        # Embed Sistema de Guilds
        embed_guilds = discord.Embed(
            title="⚔️ SISTEMA DE GUILDS E RAIDS",
            description=(
                "Una forças e domine o servidor com sua guild!\n\n"
                "**Comandos disponíveis:**\n"
                "`/guild_criar <nome>` — Crie sua guild\n"
                "`/guild_aliar-se <guild>` — Proponha aliança\n"
                "`/guild_raid_iniciar <guild>` — Inicie uma raid\n"
                "`/guild_raid_status` — Status das raids\n\n"
                "🤝 Sistema de Alianças\n"
                "• Forme alianças com até 5 guilds\n• Apoio mútuo em raids e defesas\n• Bônus estratégicos em batalhas\n• Defesa conjunta contra invasores\n\n"
                "⚔️ Sistema de Raids\n"
                "• Ataque outras guilds por recursos\n• Estratégias de ataque e defesa\n• Recompensas em XP e coins\n• Cooldown de 24h entre raids\n\n"
                "🎯 Estratégias de Batalha\n"
                "*Una-se aos seus irmãos e escreva sua lenda! 🛡️*"
            ),
            color=0xFF4500
        )
        await ctx.send(embed=embed_guilds)

        embed_xp = discord.Embed(
            title="📊 SISTEMA DE XP E RANKING",
            description=(
                "Mostre sua força e dedicação subindo no ranking!\n"
                "Ganhe XP conversando e participando de canais de voz.\n\n"
                "**Comandos disponíveis:**\n"
                "`/xp [membro]` — Mostra seu XP e nível atual\n"
                "`/ranking` — Ranking dos maiores guerreiros!\n"
                "`/status_voz` — Status do sistema de voz\n\n"
                "🎧 Sistema de Voz\n"
                "+15.000 XP a cada 5 minutos (Use `/status_voz`)\n\n"
                "💬 Sistema de Mensagens\n"
                "+5.000 XP por mensagem (cooldown de 10 segundos)\n\n"
                "🎯 Sistema de Vitórias\n"
                "+10.000 XP por vitória em batalhas\n\n"
                "🛡️ Progressão de Níveis\n"
                "Nível 5 - Aprendiz Viking 🪓\n"
                "Nível 10 - Guerreiro Nórdico ⚔️\n"
                "Nível 20 - Berserker 🛡️\n"
                "Nível 30 - Herói de Midgard 🌟\n"
                "Nível 40 - Campeão de Asgard 🏆\n"
                "Nível 50 - Guerreiro de Valhalla 🏰\n\n"
                "*Cargos atribuídos automaticamente!*\n\n"
                "💡 Dicas de Progresso\n"
                "• Mensagens: +5.000 XP a cada 10s\n• Voz: +15.000 XP a cada 5min\n• Vitórias: +10.000 XP extra\n• Atividade constante sobe rápido!\n• Verifique progresso com `/xp`\n\n"
                "🚀 Multiplicadores\n"
                "• Premium: até 6x XP\n• Guild: até 5x XP\n• Dobro XP: 2x temporário\n\n"
                "*Mostre seu valor, guerreiro! Que Odin guie sua jornada! ⚔️*"
            ),
            color=0x1E90FF
        )
        await ctx.send(embed=embed_xp)
        
        embed_aventura = discord.Embed(
            title="🗺️ SISTEMA DE AVENTURA",
            description=(
                "Embarque em missões épicas e enfrente desafios únicos!\n\n"
                "**Comandos Disponíveis:**\n"
                "`/aventura` — Inicia/resgata uma aventura\n"
                "`/aventura_status` — Ver status da aventura atual\n\n"
                "🎯 Tipos de Situações:\n"
                "• **Combate** ⚔️ - Enfrente esqueletos ou piratas\n"
                "• **Tesouro** 💰 - Encontre baús perdidos\n\n"
                "⏰ Sistema de Tempo:\n"
                "• Duração: **4 horas** por missão\n"
                "• Progresso em tempo real\n"
                "• Notificação automática quando pronta\n"
                "• Use `/aventura` para resgatar recompensas\n\n"
            
                "📊 Características do Sistema:\n"
                "• Notificações Automáticas via DM quando aventura pronta\n"
                "• Views Permanentes - botões funcionam mesmo após reinício do bot\n"
                "• Sistema de Logs completo no canal dedicado\n"
                "• Remoção Automática de aventuras abandonadas (após 24h)\n"
                "• Verificação em Tempo Real do status das aventuras\n\n"
                "*A glória espera os corajosos! Sua lenda começa aqui! 🌟*"
            ),
            color=0x00FF7F
        )
        
        await ctx.send(embed=embed_aventura)
                        

async def setup(bot: commands.Bot):
    await bot.add_cog(StatusCog(bot))
