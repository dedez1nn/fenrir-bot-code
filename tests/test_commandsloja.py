import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
import discord
from discord.ext import commands
import asyncio

from cogs.comands_loja import ComandosLojaCog

@pytest.fixture
def bot():
    bot = Mock(spec=commands.Bot)
    bot.get_cog = Mock()
    bot.get_channel = Mock()
    bot.add_view = Mock()
    return bot

@pytest.fixture
def comandos_loja_cog(bot):
    cog = ComandosLojaCog(bot)
    cog.cooldowns = {}
    return cog

@pytest.fixture
def interaction():
    interaction = AsyncMock()
    interaction.user = Mock()
    interaction.user.id = 123456789
    interaction.user.mention = "@usuario"
    interaction.user.display_name = "Usuario"
    interaction.user.display_avatar.url = "https://avatar.url"
    interaction.channel = Mock()
    interaction.channel.id = 1426205118293868748
    interaction.channel.send = AsyncMock()
    interaction.guild = Mock()
    interaction.guild.me = Mock()
    interaction.guild.me.permissions = Mock()
    interaction.response = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction

@pytest.fixture
def vitima():
    vitima = Mock(spec=discord.Member)
    vitima.id = 987654321
    vitima.mention = "@vitima"
    vitima.display_name = "Vitima"
    vitima.bot = False
    return vitima

@pytest.fixture
def canal():
    canal = Mock(spec=discord.TextChannel)
    canal.id = 123456789
    canal.name = "nome-original"
    canal.mention = "<#123456789>"
    canal.edit = AsyncMock()
    canal.send = AsyncMock()
    canal.permissions_for = Mock()
    canal.permissions_for.return_value.manage_channels = True
    canal.fetch_message = AsyncMock()
    return canal

@pytest.fixture
def mock_cooldown_cog():
    mock = AsyncMock()
    mock.verificar_compra = AsyncMock(return_value=True)
    return mock

@pytest.fixture
def mock_coins_cog():
    mock = AsyncMock()
    mock.obter_coins = AsyncMock(return_value=10000)
    mock.adicionar_coins = AsyncMock(return_value=True)
    mock.remover_coins = AsyncMock(return_value=True)
    return mock

class TestComandosLojaCog:

    def test_get_cooldown_cog(self, comandos_loja_cog, mock_cooldown_cog):
        comandos_loja_cog.bot.get_cog.return_value = mock_cooldown_cog
        resultado = comandos_loja_cog.get_cooldown_cog()
        assert resultado == mock_cooldown_cog

    @pytest.mark.asyncio
    async def test_verificar_compra_sucesso(self, comandos_loja_cog, mock_cooldown_cog):
        # Evita a chamada real ao cooldown_cog, força retorno True
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True):
            resultado = await comandos_loja_cog.verificar_compra(123456, 3)
            assert resultado is True

    @pytest.mark.asyncio
    async def test_verificar_compra_cog_inexistente(self, comandos_loja_cog):
        comandos_loja_cog.bot.get_cog.return_value = None
        resultado = await comandos_loja_cog.verificar_compra(123456, 3)
        assert resultado is False

    @pytest.mark.asyncio
    async def test_verificar_cooldown_primeira_vez(self, comandos_loja_cog):
        with patch('time.time', return_value=1000):
            resultado = await comandos_loja_cog.verificar_cooldown(123456, "teste", 60)
            assert resultado == 0
            assert comandos_loja_cog.cooldowns["123456_teste"] == 1060

    @pytest.mark.asyncio
    async def test_verificar_cooldown_ainda_ativo(self, comandos_loja_cog):
        comandos_loja_cog.cooldowns["123456_teste"] = 1060
        with patch('time.time', return_value=1020):
            resultado = await comandos_loja_cog.verificar_cooldown(123456, "teste", 60)
            assert resultado == 40

    @pytest.mark.asyncio
    async def test_verificar_cooldown_expirado(self, comandos_loja_cog):
        comandos_loja_cog.cooldowns["123456_teste"] = 1000
        with patch('time.time', return_value=1100):
            resultado = await comandos_loja_cog.verificar_cooldown(123456, "teste", 60)
            assert resultado == 0
            assert comandos_loja_cog.cooldowns["123456_teste"] == 1160

    @pytest.mark.asyncio
    async def test_roubar_canal_errado(self, comandos_loja_cog, interaction, vitima):
        interaction.channel.id = 999999
        await comandos_loja_cog.roubar.callback(comandos_loja_cog, interaction, vitima)
        interaction.response.send_message.assert_called()
        assert "use esse **comando** apenas em" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_roubar_sem_item_comprado(self, comandos_loja_cog, interaction, vitima):
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=False):
            await comandos_loja_cog.roubar.callback(comandos_loja_cog, interaction, vitima)
            interaction.response.send_message.assert_called_with(
                "❌ **Você precisa comprar o item 'Roubo de Coins' na loja para usar este comando!**\n"
                "💎 Use `/loja` para ver os itens disponíveis.",
                ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_roubar_cooldown_vitima_ativo(self, comandos_loja_cog, interaction, vitima):
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=3600):
            await comandos_loja_cog.roubar.callback(comandos_loja_cog, interaction, vitima)
            interaction.response.send_message.assert_called()
            assert "Cooldown ativo" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_roubar_si_mesmo(self, comandos_loja_cog, interaction, vitima):
        vitima.id = interaction.user.id
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=0):
            await comandos_loja_cog.roubar.callback(comandos_loja_cog, interaction, vitima)
            interaction.response.send_message.assert_called_with(
                "🤨 **Você não pode roubar a si mesmo!**",
                ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_roubar_bot(self, comandos_loja_cog, interaction, vitima):
        vitima.bot = True
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=0):
            await comandos_loja_cog.roubar.callback(comandos_loja_cog, interaction, vitima)
            interaction.response.send_message.assert_called_with(
                "🤖 **Bots não possuem coins para roubar!**",
                ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_roubar_sistema_coins_indisponivel(self, comandos_loja_cog, interaction, vitima):
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=0), \
             patch.object(comandos_loja_cog.bot, 'get_cog', return_value=None):
            await comandos_loja_cog.roubar.callback(comandos_loja_cog, interaction, vitima)
            interaction.response.send_message.assert_called_with(
                "❌ **Sistema de coins indisponível no momento.**",
                ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_roubar_vitima_sem_coins_suficientes(self, comandos_loja_cog, interaction, vitima, mock_coins_cog):
        mock_coins_cog.obter_coins = AsyncMock(return_value=50)
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=0), \
             patch.object(comandos_loja_cog.bot, 'get_cog', return_value=mock_coins_cog):
            await comandos_loja_cog.roubar.callback(comandos_loja_cog, interaction, vitima)
            interaction.response.send_message.assert_called()
            assert "não tem coins suficientes" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_roubar_sucesso(self, comandos_loja_cog, interaction, vitima, mock_coins_cog):
        mock_coins_cog.obter_coins = AsyncMock(return_value=10000)
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=0), \
             patch.object(comandos_loja_cog.bot, 'get_cog', return_value=mock_coins_cog), \
             patch('random.random', return_value=0.6), \
             patch('discord.Embed'), \
             patch('discord.utils.utcnow', return_value=datetime.now(timezone.utc)), \
             patch.object(comandos_loja_cog.bot, 'get_channel', return_value=None):

            await comandos_loja_cog.roubar.callback(comandos_loja_cog, interaction, vitima)

            mock_coins_cog.remover_coins.assert_awaited_once_with(vitima.id, 4000, f"Roubado por {interaction.user}")
            mock_coins_cog.adicionar_coins.assert_awaited_once_with(interaction.user.id, 4000, f"Roubo de {vitima}")
            interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_roubar_falha(self, comandos_loja_cog, interaction, vitima, mock_coins_cog):
        mock_coins_cog.obter_coins = AsyncMock(side_effect=[10000, 5000])
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=0), \
             patch.object(comandos_loja_cog.bot, 'get_cog', return_value=mock_coins_cog), \
             patch('random.random', return_value=0.8), \
             patch('discord.Embed'), \
             patch('discord.utils.utcnow', return_value=datetime.now(timezone.utc)), \
             patch.object(comandos_loja_cog.bot, 'get_channel', return_value=None):

            await comandos_loja_cog.roubar.callback(comandos_loja_cog, interaction, vitima)

            mock_coins_cog.remover_coins.assert_awaited_with(interaction.user.id, 500, "Multa por roubo falhado")
            mock_coins_cog.adicionar_coins.assert_awaited_with(vitima.id, 500, "Compensação por tentativa de roubo")
            interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_renomear_canal_canal_errado(self, comandos_loja_cog, interaction, canal):
        interaction.channel.id = 999999
        await comandos_loja_cog.renomear_canal.callback(comandos_loja_cog, interaction, canal, "novo nome")
        interaction.response.send_message.assert_called()
        assert "use esse **comando** apenas em" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_renomear_canal_sem_item(self, comandos_loja_cog, interaction, canal):
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=False):
            await comandos_loja_cog.renomear_canal.callback(comandos_loja_cog, interaction, canal, "novo nome")
            interaction.response.send_message.assert_called_with(
                "❌ **Você precisa comprar o item 'Renomear Canal' na loja para usar este comando!**",
                ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_renomear_canal_cooldown_ativo(self, comandos_loja_cog, interaction, canal):
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=3600):
            await comandos_loja_cog.renomear_canal.callback(comandos_loja_cog, interaction, canal, "novo nome")
            interaction.response.send_message.assert_called()
            assert "Cooldown ativo" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_renomear_canal_nome_invalido(self, comandos_loja_cog, interaction, canal):
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=0):
            await comandos_loja_cog.renomear_canal.callback(comandos_loja_cog, interaction, canal, "a")
            interaction.response.send_message.assert_called_with(
                "❌ **O nome do canal deve ter entre 2 e 25 caracteres!**",
                ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_renomear_canal_sem_permissao_bot(self, comandos_loja_cog, interaction, canal):
        canal.permissions_for.return_value.manage_channels = False
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=0):
            await comandos_loja_cog.renomear_canal.callback(comandos_loja_cog, interaction, canal, "nome valido")
            interaction.response.send_message.assert_called_with(
                "❌ **Não tenho permissão para gerenciar canais!**",
                ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_renomear_canal_sucesso(self, comandos_loja_cog, interaction, canal):
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=0), \
             patch.object(comandos_loja_cog.bot, 'get_channel', return_value=None), \
             patch('discord.Embed'), \
             patch('discord.utils.utcnow', return_value=datetime.now(timezone.utc)), \
             patch('asyncio.sleep', return_value=None):

            await comandos_loja_cog.renomear_canal.callback(comandos_loja_cog, interaction, canal, "Novo Nome")

            canal.edit.assert_any_call(name="Novo Nome")
            canal.edit.assert_any_call(name="nome-original")
            assert canal.edit.call_count == 2
            interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_criar_enquete_canal_errado(self, comandos_loja_cog, interaction):
        interaction.channel.id = 999999
        await comandos_loja_cog.criar_enquete.callback(comandos_loja_cog, interaction, "Pergunta?", 60)
        interaction.response.send_message.assert_called()
        assert "use esse **comando** apenas em" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_criar_enquete_sem_item(self, comandos_loja_cog, interaction):
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=False):
            await comandos_loja_cog.criar_enquete.callback(comandos_loja_cog, interaction, "Pergunta?", 60)
            interaction.response.send_message.assert_called_with(
                "❌ **Você precisa comprar o item 'Enquete' na loja para usar este comando!**",
                ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_criar_enquete_cooldown(self, comandos_loja_cog, interaction):
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=1800):
            await comandos_loja_cog.criar_enquete.callback(comandos_loja_cog, interaction, "Pergunta?", 60)
            interaction.response.send_message.assert_called()
            assert "Cooldown ativo" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_criar_enquete_duracao_invalida(self, comandos_loja_cog, interaction):
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=0):
            await comandos_loja_cog.criar_enquete.callback(comandos_loja_cog, interaction, "Pergunta?", 1500)
            interaction.response.send_message.assert_called_with(
                "❌ **A duração deve ser entre 1 minuto e 24 horas (1440 minutos)!**",
                ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_criar_enquete_sucesso(self, comandos_loja_cog, interaction):
        mensagem_mock = AsyncMock()
        mensagem_mock.add_reaction = AsyncMock()
        mensagem_mock.jump_url = "https://discord.com/channels/.../..."
        interaction.channel.send.return_value = mensagem_mock

        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=0), \
             patch.object(comandos_loja_cog.bot, 'get_channel', return_value=None), \
             patch('discord.Embed'), \
             patch('discord.utils.utcnow', return_value=datetime.now(timezone.utc)):

            await comandos_loja_cog.criar_enquete.callback(comandos_loja_cog, interaction, "Pergunta?", 30)

            interaction.channel.send.assert_called_once()
            mensagem_mock.add_reaction.assert_any_call("✅")
            mensagem_mock.add_reaction.assert_any_call("❌")
            interaction.response.send_message.assert_called_once()
            assert "Enquete criada com sucesso" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_fixar_mensagem_canal_errado(self, comandos_loja_cog, interaction):
        interaction.channel.id = 999999
        await comandos_loja_cog.fixar_mensagem.callback(comandos_loja_cog, interaction, "123456789")
        interaction.response.send_message.assert_called()
        assert "use esse **comando** apenas em" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_fixar_mensagem_sem_item(self, comandos_loja_cog, interaction):
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=False):
            await comandos_loja_cog.fixar_mensagem.callback(comandos_loja_cog, interaction, "123456789")
            interaction.response.send_message.assert_called_with(
                "❌ **Você precisa comprar o item 'Fixar Mensagem' na loja para usar este comando!**",
                ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_fixar_mensagem_cooldown(self, comandos_loja_cog, interaction):
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=3600):
            await comandos_loja_cog.fixar_mensagem.callback(comandos_loja_cog, interaction, "123456789")
            interaction.response.send_message.assert_called()
            assert "Cooldown ativo" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_fixar_mensagem_nao_encontrada(self, comandos_loja_cog, interaction, canal):
        interaction.channel.fetch_message = AsyncMock(side_effect=discord.NotFound(Mock(), "not found"))
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=0):
            await comandos_loja_cog.fixar_mensagem.callback(comandos_loja_cog, interaction, "999")
            interaction.response.send_message.assert_called_with(
                "❌ **Mensagem não encontrada! Certifique-se de que o ID está correto.**",
                ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_fixar_mensagem_ja_fixada(self, comandos_loja_cog, interaction, canal):
        mensagem_mock = AsyncMock()
        mensagem_mock.pinned = True
        interaction.channel.fetch_message = AsyncMock(return_value=mensagem_mock)
        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=0):
            await comandos_loja_cog.fixar_mensagem.callback(comandos_loja_cog, interaction, "123456789")
            interaction.response.send_message.assert_called_with(
                "❌ **Esta mensagem já está fixada!**",
                ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_fixar_mensagem_sucesso(self, comandos_loja_cog, interaction, canal):
        mensagem_mock = AsyncMock()
        mensagem_mock.pinned = False
        mensagem_mock.author = Mock()
        mensagem_mock.author.mention = "@autor"
        mensagem_mock.content = "Conteúdo da mensagem"
        mensagem_mock.pin = AsyncMock()
        mensagem_mock.unpin = AsyncMock()
        interaction.channel.fetch_message = AsyncMock(return_value=mensagem_mock)

        with patch.object(comandos_loja_cog, 'verificar_compra', return_value=True), \
             patch.object(comandos_loja_cog, 'verificar_cooldown', return_value=0), \
             patch.object(comandos_loja_cog.bot, 'get_channel', return_value=None), \
             patch('discord.Embed'), \
             patch('discord.utils.utcnow', return_value=datetime.now(timezone.utc)), \
             patch('asyncio.sleep', return_value=None):

            await comandos_loja_cog.fixar_mensagem.callback(comandos_loja_cog, interaction, "123456789")

            mensagem_mock.pin.assert_called_once()
            interaction.response.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_setup():
    bot = AsyncMock()
    with patch('cogs.comands_loja.ComandosLojaCog') as mock_cog:
        from cogs.comands_loja import setup as setup_func
        await setup_func(bot)
        mock_cog.assert_called_once_with(bot)
        bot.add_cog.assert_called_once()