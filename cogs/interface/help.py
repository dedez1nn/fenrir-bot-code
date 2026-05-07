import discord
from discord import app_commands
from discord.ext import commands

PAGES = [
    {
        "title": "Riot API — League of Legends & TFT",
        "emoji": "🎮",
        "color": discord.Color.from_rgb(200, 155, 60),
        "commands": [
            ("/lol-perfil <nick>", "Exibe o perfil completo de um invocador no LoL"),
            ("/lol-rank <nick>", "Exibe o rank atual de um invocador no LoL"),
            ("/lol-historico <nick> [quantidade]", "Histórico de partidas (1-10, padrão 5)"),
            ("/lol-maestria <nick>", "Top 5 maestrias de campeões de um invocador"),
            ("/lol-rotacao", "Campeões gratuitos desta semana no LoL"),
            ("/lol-aovivo <nick>", "Exibe a partida em andamento de um invocador"),
            ("/lol-comparar <nick1> <nick2>", "Compara o rank de dois invocadores"),
            ("/tft-rank <nick>", "Exibe o rank de um invocador no TFT"),
            ("/tft-historico <nick> [quantidade]", "Histórico de partidas de TFT (1-10, padrão 5)"),
        ],
    },
    {
        "title": "Steam API",
        "emoji": "🖥️",
        "color": discord.Color.from_rgb(27, 40, 56),
        "commands": [
            ("/steam-perfil <steamid>", "Exibe o perfil público de um usuário da Steam"),
            ("/steam-biblioteca <steamid>", "Exibe a biblioteca de jogos de um usuário"),
            ("/steam-recentes <steamid>", "Jogos jogados nas últimas 2 semanas"),
            ("/steam-conquistas <steamid> <appid>", "Conquistas de um usuário em um jogo específico"),
            ("/steam-amigos <steamid>", "Lista os amigos online de um usuário"),
            ("/steam-bans <steamid>", "Verifica o histórico de bans de um usuário"),
            ("/steam-jogo <appid>", "Exibe informações de um jogo na Steam"),
        ],
    },
    {
        "title": "Notícias",
        "emoji": "📰",
        "color": discord.Color.blue(),
        "commands": [
            ("/noticias [categoria]", "Exibe as principais notícias do momento"),
            ("/buscar-noticias <query> [em_portugues]", "Busca notícias sobre um assunto específico"),
        ],
    },
    {
        "title": "Coins",
        "emoji": "🪙",
        "color": discord.Color.gold(),
        "commands": [
            ("/coins [membro]", "Ver suas coins ou as de outro usuário"),
            ("/daily", "Resgatar suas coins diárias"),
            ("/transferir <membro> <quantidade>", "Transferir coins para outro usuário"),
            ("/ranking_coins", "Exibe o ranking de coins do servidor"),
            ("/adicionar_coins <membro> <quantidade>", "Adicionar coins a um usuário *(ADM)*"),
            ("/remover_coins <membro> <quantidade>", "Remover coins de um usuário *(ADM)*"),
        ],
    },
    {
        "title": "Loja",
        "emoji": "🛒",
        "color": discord.Color.from_rgb(255, 165, 0),
        "commands": [
            ("/loja", "Ver os itens disponíveis na loja"),
            ("/comprar <item_id>", "Comprar um item da loja pelo ID"),
            ("/adicionar_item <nome> <preco> <descricao>", "Adicionar um item à loja *(ADM)*"),
            ("/remover_item <numero_item> [motivo]", "Remover um item da loja *(ADM)*"),
            ("/limpar_loja [motivo]", "Remover TODOS os itens da loja *(ADM)*"),
        ],
    },
    {
        "title": "Itens de Loja",
        "emoji": "🎭",
        "color": discord.Color.purple(),
        "commands": [
            ("/roubar <vitima>", "Rouba 40% das coins de um usuário *(requer compra)*"),
            ("/renomear_canal <canal> <novo_nome>", "Renomeia um canal por 1 hora *(requer compra)*"),
            ("/criar_enquete <pergunta> [duracao]", "Cria uma enquete SIM/NÃO *(requer compra)*"),
            ("/fixar_mensagem <mensagem_id>", "Fixa uma mensagem por 1 hora *(requer compra)*"),
        ],
    },
    {
        "title": "Premium",
        "emoji": "⭐",
        "color": discord.Color.from_rgb(255, 215, 0),
        "commands": [
            ("/premium", "Mostra informações sobre os planos premium"),
            ("/premium_remover <usuario>", "Remove plano premium de um usuário *(ADM)*"),
            ("/premium_adicionar <usuario> <plano> [dias]", "Adiciona plano premium a um usuário *(ADM)*"),
        ],
    },
    {
        "title": "XP & Progressão",
        "emoji": "✨",
        "color": discord.Color.from_rgb(100, 200, 255),
        "commands": [
            ("/xp [membro]", "Mostra o seu XP ou de outro membro"),
            ("/status_dobro_xp", "Mostra o status do seu bônus de dobro de XP"),
            ("/set_titulo <membro> <titulo>", "Configura título personalizado para um membro *(ADM)*"),
            ("/set_premium <membro> <plano>", "Configura plano premium para um membro *(ADM)*"),
            ("/reset-xp-all", "Zera o XP de TODOS os membros *(ADM)*"),
            ("/reset-xp <membro>", "Zera o XP de um membro específico *(ADM)*"),
            ("/retirar-xp <membro> <quantidade>", "Remove XP de um membro *(ADM)*"),
        ],
    },
    {
        "title": "Aventura",
        "emoji": "⚔️",
        "color": discord.Color.from_rgb(139, 69, 19),
        "commands": [
            ("/aventura", "Inicie uma aventura ou resgate uma pendente"),
            ("/aventura_status", "Verifique o status da sua aventura atual"),
        ],
    },
    {
        "title": "Guild",
        "emoji": "🏰",
        "color": discord.Color.from_rgb(70, 130, 180),
        "commands": [
            ("/guild_criar <nome>", "Cria uma nova guild"),
            ("/guild_info [nome]", "Mostra informações da guild"),
            ("/guild_membros", "Lista todos os membros da sua guild"),
            ("/guild_sair", "Sai da guild atual"),
            ("/guild_ranking", "Mostra o ranking das guilds"),
            ("/guild_progresso", "Mostra a progressão de níveis da guild"),
            ("/guild_convidar <usuario>", "Convida um usuário para a guild"),
            ("/guild_aceitar", "Aceita um convite para uma guild"),
            ("/guild_saldo", "Mostra o saldo do banco da guild"),
            ("/guild_depositar <quantidade>", "Deposita coins no banco da guild"),
            ("/guild_retirar <quantidade>", "Retira coins do banco da guild"),
            ("/guild_promover <membro>", "Promove um membro da guild"),
            ("/guild_rebaixar <membro>", "Rebaixa um membro da guild"),
            ("/guild_listar", "Lista todas as guilds com seus IDs *(ADM)*"),
            ("/guild_adicionar_xp <quantidade>", "Adiciona XP à guild *(DEV)*"),
        ],
    },
    {
        "title": "Moderação",
        "emoji": "🛡️",
        "color": discord.Color.red(),
        "commands": [
            ("/addrole <usuario> <cargo>", "Adiciona um cargo a um usuário"),
            ("/addrole-all <cargo>", "Adiciona um cargo a todos os usuários"),
            ("/removerole <usuario> <cargo>", "Remove um cargo de um usuário"),
            ("/removerole-all <cargo>", "Remove um cargo de todos os usuários"),
            ("/limpar <mensagens>", "Apaga o número de mensagens desejado do canal"),
            ("/manutencao", "Envia mensagem de reinício *(DEVS)*"),
        ],
    },
]


class HelpView(discord.ui.View):
    def __init__(self, page: int = 0):
        super().__init__(timeout=120)
        self.page = page
        self.total = len(PAGES)
        self._update_buttons()

    def _update_buttons(self):
        self.btn_first.disabled = self.page == 0
        self.btn_prev.disabled = self.page == 0
        self.btn_counter.label = f"{self.page + 1} / {self.total}"
        self.btn_next.disabled = self.page >= self.total - 1
        self.btn_last.disabled = self.page >= self.total - 1

    def build_embed(self) -> discord.Embed:
        data = PAGES[self.page]
        embed = discord.Embed(
            title=f"{data['emoji']} {data['title']}",
            color=data["color"],
        )
        lines = "\n".join(
            f"`{name}` — {desc}" for name, desc in data["commands"]
        )
        embed.description = lines
        embed.set_footer(text=f"Categoria {self.page + 1} de {self.total}")
        return embed

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, row=0)
    async def btn_first(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary, row=0)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="1 / 1", style=discord.ButtonStyle.primary, disabled=True, row=0)
    async def btn_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary, row=0)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.total - 1:
            self.page += 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def btn_last(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = self.total - 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Lista todos os comandos do bot por categoria")
    async def help(self, interaction: discord.Interaction):
        if await self.bot.guard_channel(interaction):
            return

        view = HelpView(page=0)
        await interaction.response.send_message(embed=view.build_embed(), view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
