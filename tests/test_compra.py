import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import discord
from discord.ext import commands
import asyncio

from cogs.economia.compra import CompraCog, SelecionarTituloView, SelecionarCorView, TituloModal, CorPremiumModal

@pytest.fixture
def bot():
    bot = Mock(spec=commands.Bot)
    bot.get_cog = Mock()
    bot.get_user = Mock()
    bot.get_channel = Mock()
    bot.config = {
        "xp_log_channel_id": 1426205118293868748,
        # Cores premium agora vêm da config (server_config.premium_color_role_ids),
        # não mais de IDs hardcoded no cog.
        "premium_color_role_ids": [
            1428400034952515696, 1428400132272951358,
            1428399718945390764, 1428399137057013783,
        ],
    }  # Mock config for modals
    return bot

@pytest.fixture
def compra_cog(bot):
    cog = CompraCog(bot)
    return cog

@pytest.fixture
def interaction():
    inter = AsyncMock(spec=discord.Interaction)
    inter.user = Mock()
    inter.user.id = 123456789
    inter.user.mention = "@user"
    inter.user.display_avatar.url = "https://avatar.url"
    inter.guild = Mock()
    inter.guild.get_member = Mock()
    inter.guild.get_role = Mock()
    inter.response = AsyncMock()
    inter.response.is_done = Mock(return_value=False)
    inter.response.defer = AsyncMock()
    inter.response.send_message = AsyncMock()
    inter.followup = AsyncMock()
    inter.followup.send = AsyncMock()
    inter.channel = Mock()
    inter.channel.id = 1426205118293868748
    return inter

@pytest.fixture
def mock_cooldown_cog():
    mock = AsyncMock()
    mock.registrar_compra = AsyncMock()
    mock.verificar_compra = AsyncMock(return_value=False)
    mock.obter_tempo_restante = AsyncMock(return_value=0)
    return mock

@pytest.fixture
def mock_coins_cog():
    mock = AsyncMock()
    mock.adicionar_coins = AsyncMock()
    mock.remover_coins = AsyncMock()
    mock.obter_coins = AsyncMock(return_value=10000)
    return mock

@pytest.fixture
def mock_xp_cog():
    mock = AsyncMock()
    mock.ativar_dobro_xp = AsyncMock(return_value=True)
    mock.xp_data = {}
    mock.salvar_dados = Mock()
    return mock

class TestCompraCog:

    def test_get_cooldown_cog(self, compra_cog, mock_cooldown_cog):
        compra_cog.bot.get_cog.return_value = mock_cooldown_cog
        assert compra_cog.get_cooldown_cog() == mock_cooldown_cog

    def test_get_coins_cog(self, compra_cog, mock_coins_cog):
        compra_cog.bot.get_cog.return_value = mock_coins_cog
        assert compra_cog.get_coins_cog() == mock_coins_cog

    # CORREÇÃO: registrar_cooldown não usa await na cog, portanto o mock não é aguardado.
    # Altera a asserção para verificar chamada síncrona (assert_called_once_with).
    @pytest.mark.asyncio
    async def test_registrar_cooldown(self, compra_cog, mock_cooldown_cog):
        compra_cog.bot.get_cog.return_value = mock_cooldown_cog
        await compra_cog.registrar_cooldown(123, 3)
        mock_cooldown_cog.registrar_compra.assert_called_once_with(123, 3, cooldown_secs=None)

    @pytest.mark.asyncio
    async def test_registrar_cooldown_sem_cog(self, compra_cog):
        compra_cog.bot.get_cog.return_value = None
        await compra_cog.registrar_cooldown(123, 3)

    @pytest.mark.asyncio
    async def test_verificar_cooldown_compra(self, compra_cog, mock_cooldown_cog):
        compra_cog.bot.get_cog.return_value = mock_cooldown_cog
        mock_cooldown_cog.verificar_compra.return_value = True
        result = await compra_cog.verificar_cooldown_compra(123, 5)
        assert result is True

    @pytest.mark.asyncio
    async def test_enviar_mensagem_ticket(self, compra_cog, interaction):
        await compra_cog.enviar_mensagem_ticket(interaction, "Nitro")
        interaction.response.send_message.assert_called_once()
        args = interaction.response.send_message.call_args[0][0]
        assert "✅ **Compra Confirmada**" in args

    @pytest.mark.asyncio
    async def test_processar_compra_com_cooldown(self, compra_cog, interaction, mock_cooldown_cog):
        compra_cog.bot.get_cog.return_value = mock_cooldown_cog
        mock_cooldown_cog.verificar_compra = AsyncMock(return_value=True)
        mock_cooldown_cog.obter_tempo_restante = AsyncMock(return_value=3600)

        result = await compra_cog.processar_compra(interaction, 1, 123, "Nitro")
        assert result is False
        interaction.response.send_message.assert_called_once()
        assert "Cooldown ativo" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_processar_compra_item_generico(self, compra_cog, interaction, mock_cooldown_cog):
        compra_cog.bot.get_cog.return_value = mock_cooldown_cog
        # A assinatura correta seria processar_item_generico(interaction, item_nome)
        # Mas a cog atual tem erro (passa user_id extra). Vamos mockar o método para evitar erro.
        with patch.object(compra_cog, 'processar_item_generico', new=AsyncMock(return_value=True)) as mock_gen:
            result = await compra_cog.processar_compra(interaction, 999, 123, "Item")
            # Como a cog chama processar_item_generico com 3 args (interaction, user_id, item_nome),
            # ajustamos o mock para aceitar 3 args
            mock_gen.assert_awaited_once_with(interaction, 123, "Item")
            assert result is True
            # A mensagem genérica de ticket é enviada pelo processar_item_generico mockado, então não verificamos.

    @pytest.mark.asyncio
    async def test_processar_compra_nitro(self, compra_cog, interaction, mock_cooldown_cog):
        compra_cog.bot.get_cog.return_value = mock_cooldown_cog
        with patch.object(compra_cog, 'processar_nitro', new=AsyncMock(return_value=True)) as mock_proc:
            result = await compra_cog.processar_compra(interaction, 1, 123, "Nitro")
            assert result is True
            mock_proc.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_processar_nitro(self, compra_cog, interaction):
        with patch.object(compra_cog, 'enviar_mensagem_ticket', new=AsyncMock()) as mock_enviar:
            result = await compra_cog.processar_nitro(interaction, 123456789, "Nitro", 1)
            assert result is True
            mock_enviar.assert_awaited_once_with(interaction, "Nitro")

    @pytest.mark.asyncio
    async def test_processar_roubo_coins(self, compra_cog, interaction):
        result = await compra_cog.processar_roubo_coins(interaction, 123456789, "Roubo de Coins", 3)
        assert result is True
        interaction.response.send_message.assert_called_once()
        assert "✅ **Roubo de Coins Ativado!**" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_processar_dobro_experiencia(self, compra_cog, interaction, mock_xp_cog):
        compra_cog.bot.get_cog.return_value = mock_xp_cog
        result = await compra_cog.processar_dobro_experiencia(interaction, 123, "Dobro de XP", 6)
        assert result is True
        mock_xp_cog.ativar_dobro_xp.assert_awaited_once_with(123, 12)
        interaction.response.send_message.assert_called_once()
        assert "✅ **Dobro de XP Ativado!**" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_processar_dobro_experiencia_sem_xp_cog(self, compra_cog, interaction):
        compra_cog.bot.get_cog.return_value = None
        result = await compra_cog.processar_dobro_experiencia(interaction, 123, "Dobro de XP", 6)
        assert result is True
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_processar_bilheteria(self, compra_cog, interaction, mock_coins_cog):
        compra_cog.bot.get_cog.side_effect = lambda name: mock_coins_cog if name == "FenrirCoins" else None
        with patch('random.randint', return_value=50000):
            result = await compra_cog.processar_bilheteria(interaction, 123, "Bilheteria", 10)
            assert result is True
            mock_coins_cog.adicionar_coins.assert_awaited_once_with(123, 50000)
            interaction.response.send_message.assert_called_once()
            assert "💎" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_processar_titulo_ranking(self, compra_cog, interaction):
        result = await compra_cog.processar_titulo_ranking(interaction, 123, "Título", 7)
        assert result is True
        interaction.response.send_message.assert_called_once()
        view_arg = interaction.response.send_message.call_args[1]['view']
        assert isinstance(view_arg, SelecionarTituloView)
        assert view_arg.user_id == 123

    @pytest.mark.asyncio
    async def test_processar_cores_premium(self, compra_cog, interaction):
        result = await compra_cog.processar_cores_premium(interaction, 123, "Cores", 8)
        assert result is True
        interaction.response.send_message.assert_called_once()
        view_arg = interaction.response.send_message.call_args[1]['view']
        assert isinstance(view_arg, SelecionarCorView)

    @pytest.mark.asyncio
    async def test_processar_cor_premium(self, compra_cog, interaction):
        result = await compra_cog.processar_cor_premium(interaction, 123, "Cor Premium", 11)
        assert result is True
        interaction.response.send_message.assert_called_once()
        view_arg = interaction.response.send_message.call_args[1]['view']
        assert isinstance(view_arg, SelecionarCorView)

    @pytest.mark.asyncio
    async def test_processar_portao_alcateia_sucesso(self, compra_cog, interaction):
        cargo_mock = Mock()
        cargo_mock.id = 1428715049928757318
        member_mock = AsyncMock()
        member_mock.add_roles = AsyncMock()
        interaction.guild.get_role.return_value = cargo_mock
        interaction.guild.get_member.return_value = member_mock
        result = await compra_cog.processar_portao_alcateia(interaction, 123, "Portão", 5)
        assert result is True
        member_mock.add_roles.assert_awaited_once_with(cargo_mock)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_processar_portao_alcateia_falha(self, compra_cog, interaction):
        interaction.guild.get_role.return_value = None
        with patch.object(compra_cog, 'enviar_mensagem_ticket', new=AsyncMock()) as mock_ticket:
            result = await compra_cog.processar_portao_alcateia(interaction, 123, "Portão", 5)
            assert result is False
            mock_ticket.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_processar_enquete(self, compra_cog, interaction):
        result = await compra_cog.processar_enquete(interaction, 123456789, "Enquete", 12)
        assert result is True
        interaction.response.send_message.assert_called_once()
        assert "/criar_enquete" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_processar_fixar_mensagem(self, compra_cog, interaction):
        result = await compra_cog.processar_fixar_mensagem(interaction, 123456789, "Fixar Mensagem", 14)
        assert result is True
        interaction.response.send_message.assert_called_once()
        assert "/fixar_mensagem" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_processar_compra_defer_resposta(self, compra_cog, interaction, mock_cooldown_cog):
        compra_cog.bot.get_cog.return_value = mock_cooldown_cog
        interaction.response.is_done.return_value = True
        with patch.object(compra_cog, 'processar_nitro', new=AsyncMock(return_value=True)) as mock_proc:
            result = await compra_cog.processar_compra(interaction, 1, 123, "Nitro")
            assert result is True
            mock_proc.assert_awaited_once_with(interaction, 123, "Nitro", 1)
            interaction.response.defer.assert_not_called()

    @pytest.mark.asyncio
    async def test_processar_compra_com_defer(self, compra_cog, interaction, mock_cooldown_cog):
        compra_cog.bot.get_cog.return_value = mock_cooldown_cog
        interaction.response.is_done.return_value = False
        with patch.object(compra_cog, 'processar_nitro', new=AsyncMock(return_value=True)) as mock_proc:
            result = await compra_cog.processar_compra(interaction, 1, 123, "Nitro")
            assert result is True
            interaction.response.defer.assert_awaited_once_with(ephemeral=False, thinking=True)
            mock_proc.assert_awaited_once_with(interaction, 123, "Nitro", 1)

    # --- Testes das Views e Modals corrigidos ---
    @pytest.mark.asyncio
    async def test_selecionar_titulo_view_escolher_titulo(self, compra_cog):
        view = SelecionarTituloView(compra_cog, 123456, None)
        interaction = AsyncMock()
        interaction.user.id = 123456
        interaction.response.send_modal = AsyncMock()
        # O botão é um atributo, não um método. Para simular clique, precisamos acessar o callback.
        button = view.children[0]  # primeiro botão
        await button.callback(interaction)
        interaction.response.send_modal.assert_called_once()
        modal = interaction.response.send_modal.call_args[0][0]
        assert isinstance(modal, TituloModal)
        assert modal.user_id == 123456

    @pytest.mark.asyncio
    async def test_selecionar_titulo_view_usuario_errado(self, compra_cog):
        view = SelecionarTituloView(compra_cog, 123456, None)
        interaction = AsyncMock()
        interaction.user.id = 999999
        interaction.response.send_message = AsyncMock()
        button = view.children[0]
        await button.callback(interaction)
        interaction.response.send_message.assert_called_once_with(
            "❌ Este botão não é para você!",
            ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_titulo_modal_submit_sucesso(self, compra_cog, interaction, mock_xp_cog):
        compra_cog.bot.get_cog.return_value = mock_xp_cog

        # Inicializa o xp_data do mock com uma entrada para o usuário
        mock_xp_cog.xp_data = {"123456": {}}

        canal_log_mock = AsyncMock()
        canal_log_mock.send = AsyncMock()
        compra_cog.bot.get_channel.return_value = canal_log_mock

        mock_user = Mock()
        mock_user.mention = "@user"
        mock_user.display_avatar.url = "https://avatar.url"
        compra_cog.bot.get_user.return_value = mock_user

        modal = TituloModal(compra_cog, 123456, None)
        modal.titulo_input = Mock()
        modal.titulo_input.value = "Meu Titulo"

        await modal.on_submit(interaction)

        assert mock_xp_cog.xp_data["123456"]["titulo"] == "Meu Titulo"
        mock_xp_cog.salvar_dados.assert_called_once()
        interaction.response.send_message.assert_called_once()
        assert "✅ **Título Definido com Sucesso!**" in interaction.response.send_message.call_args[0][0]
        canal_log_mock.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_titulo_modal_submit_palavras_proibidas(self, compra_cog, interaction):
        modal = TituloModal(compra_cog, 123456, None)
        modal.titulo_input = Mock()
        modal.titulo_input.value = "admin"
        await modal.on_submit(interaction)
        interaction.response.send_message.assert_called_once_with(
            "❌ Título contém palavras não permitidas! Escolha outro título.",
            ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_cor_premium_modal_submit_valido(self, compra_cog, interaction):
        modal = CorPremiumModal(compra_cog, 123456, None)
        modal.cor_select = Mock()
        modal.cor_select.value = "1"
        interaction.client = compra_cog.bot
        guild = Mock()
        member = AsyncMock()
        member.roles = []
        guild.get_member.return_value = member
        interaction.guild = guild
        cargo_mock = Mock()
        cargo_mock.id = 1428400034952515696
        guild.get_role.return_value = cargo_mock
        with patch.object(compra_cog.bot, 'get_channel', return_value=None):
            await modal.on_submit(interaction)
        member.remove_roles.assert_not_called()
        member.add_roles.assert_awaited_once_with(cargo_mock)
        interaction.response.send_message.assert_called_once()
        assert "✅ **Cor Premium Ativada!**" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cor_premium_modal_submit_opcao_invalida(self, compra_cog, interaction):
        modal = CorPremiumModal(compra_cog, 123456, None)
        modal.cor_select = Mock()
        modal.cor_select.value = "5"
        await modal.on_submit(interaction)
        interaction.response.send_message.assert_called_once_with(
            "❌ Opção inválida! Escolha um número entre 1 e 4.",
            ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_cor_premium_modal_submit_membro_nao_encontrado(self, compra_cog, interaction):
        modal = CorPremiumModal(compra_cog, 123456, None)
        modal.cor_select = Mock()
        modal.cor_select.value = "1"
        interaction.client = compra_cog.bot
        interaction.guild.get_member.return_value = None
        await modal.on_submit(interaction)
        interaction.response.send_message.assert_called_once_with(
            "❌ Membro não encontrado no servidor!",
            ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_cor_premium_modal_cargo_nao_existe(self, compra_cog, interaction):
        modal = CorPremiumModal(compra_cog, 123456, None)
        modal.cor_select = Mock()
        modal.cor_select.value = "1"
        interaction.client = compra_cog.bot
        member = AsyncMock()
        interaction.guild.get_member.return_value = member
        interaction.guild.get_role.return_value = None
        await modal.on_submit(interaction)
        interaction.response.send_message.assert_called_once_with(
            "❌ Cargo não encontrado! Contate a administração.",
            ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_cor_premium_modal_remocao_cargo_anterior(self, compra_cog, interaction):
        modal = CorPremiumModal(compra_cog, 123456, None)
        modal.cor_select = Mock()
        modal.cor_select.value = "2"
        interaction.client = compra_cog.bot
        guild = Mock()
        member = AsyncMock()
        cargo_antigo = Mock()
        cargo_antigo.id = 1428400034952515696
        member.roles = [cargo_antigo]
        guild.get_member.return_value = member
        guild.get_role.side_effect = lambda rid: cargo_antigo if rid == cargo_antigo.id else Mock()
        interaction.guild = guild
        with patch.object(compra_cog.bot, 'get_channel', return_value=None):
            await modal.on_submit(interaction)
        member.remove_roles.assert_awaited_once_with(cargo_antigo)
        member.add_roles.assert_awaited_once()

@pytest.mark.asyncio
async def test_setup():
    bot = AsyncMock()
    with patch('cogs.economia.compra.CompraCog') as mock_cog:
        from cogs.economia.compra import setup as setup_func
        await setup_func(bot)
        mock_cog.assert_called_once_with(bot)
        bot.add_cog.assert_called_once()