from unittest.mock import Mock, AsyncMock, patch

import pytest
from discord.ext import commands

from cogs.progressao.xp import XPCog
from db.config import ServerConfig


@pytest.fixture
def bot():
    bot = Mock(spec=commands.Bot)
    bot.db = None
    bot.config = None
    bot.command_prefix = "!"
    bot.get_cog = Mock(return_value=None)
    bot.get_channel = Mock(return_value=None)
    bot.get_user = Mock(return_value=None)
    bot.get_guild = Mock(return_value=None)
    bot.wait_until_ready = AsyncMock()
    bot.loop = Mock()
    bot.loop.create_task = Mock()
    return bot


@pytest.fixture
def xp_cog(bot, tmp_path):
    with patch.object(XPCog, "carregar_dados", return_value={}):
        cog = XPCog(bot)
    cog.use_db = False
    cog.user_data = {}
    cog.xp_data = cog.user_data
    cog.ARQUIVO_DADOS = str(tmp_path / "test_user_data.json")
    return cog


class TestMultiplicadorGuild:
    """Cobre a regressão do bug P0.1: await ausente em calcular_multiplicador_guild."""

    @pytest.mark.asyncio
    async def test_adicionar_xp_credita_multiplicador_guild_corretamente(self, xp_cog):
        xp_cog.user_data["123"] = {
            "xp": 0, "nivel": 1, "titulo": "Aprendiz", "dobro": False,
            "premium": None, "coins": 0, "daily_streak": 0,
            "last_daily": None, "total_ganho": 0, "guild": "guild-1",
        }

        guild_cog = Mock()
        guild_cog.calcular_multiplicador_guild = AsyncMock(return_value=1.5)
        xp_cog.bot.get_cog = Mock(side_effect=lambda nome: guild_cog if nome == "GuildSystem" else None)

        subiu_nivel = await xp_cog.adicionar_xp("123", xp_ganho=100, reason="Sistema")

        guild_cog.calcular_multiplicador_guild.assert_awaited_once_with("guild-1")
        assert subiu_nivel is False
        assert xp_cog.user_data["123"]["xp"] == pytest.approx(150.0)  # 100 * (1 + 0.5)

    @pytest.mark.asyncio
    async def test_adicionar_xp_guild_multiplicador_falha_degrada_para_1x(self, xp_cog):
        xp_cog.user_data["123"] = {
            "xp": 0, "nivel": 1, "titulo": "Aprendiz", "dobro": False,
            "premium": None, "coins": 0, "daily_streak": 0,
            "last_daily": None, "total_ganho": 0, "guild": "guild-1",
        }

        guild_cog = Mock()
        guild_cog.calcular_multiplicador_guild = AsyncMock(side_effect=RuntimeError("guild sumiu"))
        xp_cog.bot.get_cog = Mock(side_effect=lambda nome: guild_cog if nome == "GuildSystem" else None)

        subiu_nivel = await xp_cog.adicionar_xp("123", xp_ganho=100, reason="Sistema")

        assert subiu_nivel is False
        assert xp_cog.user_data["123"]["xp"] == 100  # multiplicador degradou para 1x, sem exceção


class TestAtualizarCargos:
    @pytest.mark.asyncio
    async def test_atualizar_cargos_adiciona_e_remove_por_nivel(self, xp_cog):
        role_nivel_2 = Mock(name="CargoNivel2")
        role_nivel_5 = Mock(name="CargoNivel5")
        xp_cog.cargos_por_nivel = {111: {"min": 2, "max": 4}, 222: {"min": 5, "max": None}}

        member = Mock()
        member.guild.get_role = Mock(side_effect=lambda rid: {111: role_nivel_2, 222: role_nivel_5}.get(rid))
        member.roles = [role_nivel_5]  # tinha o cargo de nível 5
        member.remove_roles = AsyncMock()
        member.add_roles = AsyncMock()
        member.send = AsyncMock()
        member.mention = "@membro"

        await xp_cog.atualizar_cargos(member, 3)  # caiu para nível 3: perde o de nível 5, ganha o de nível 2

        member.remove_roles.assert_awaited_once()
        assert role_nivel_5 in member.remove_roles.call_args.args
        member.add_roles.assert_awaited_once()
        assert role_nivel_2 in member.add_roles.call_args.args

    @pytest.mark.asyncio
    async def test_atualizar_cargos_ignora_cargo_inexistente_no_servidor(self, xp_cog):
        xp_cog.cargos_por_nivel = {999: {"min": 2, "max": None}}
        member = Mock()
        member.guild.get_role = Mock(return_value=None)  # cargo não existe mais na guild
        member.roles = []
        member.remove_roles = AsyncMock()
        member.add_roles = AsyncMock()

        await xp_cog.atualizar_cargos(member, 5)

        member.remove_roles.assert_not_awaited()
        member.add_roles.assert_not_awaited()


class TestReloadCargosPorNivel:
    """Cobre a regressão do bug P0.2: cargos_por_nivel nunca recarregado após __init__."""

    def test_carrega_do_config_atual(self, xp_cog):
        xp_cog.bot.config = ServerConfig({"levelup_role_map": [{"cargo_id": 111, "min": 2, "max": 10}]})
        assert xp_cog._carregar_cargos_por_nivel() == {111: {"min": 2, "max": 10}}

    def test_reflete_mudanca_apos_reload(self, xp_cog):
        xp_cog.bot.config = ServerConfig({"levelup_role_map": [{"cargo_id": 111, "min": 2, "max": 10}]})
        assert xp_cog._carregar_cargos_por_nivel() == {111: {"min": 2, "max": 10}}

        xp_cog.bot.config = ServerConfig({"levelup_role_map": [
            {"cargo_id": 111, "min": 2, "max": 10},
            {"cargo_id": 222, "min": 11, "max": None},
        ]})
        assert xp_cog._carregar_cargos_por_nivel() == {
            111: {"min": 2, "max": 10},
            222: {"min": 11, "max": None},
        }

    def test_sem_config_retorna_vazio(self, xp_cog):
        xp_cog.bot.config = None
        assert xp_cog._carregar_cargos_por_nivel() == {}


class TestOnMessage:
    """Cobre a regressão do bug P0.3 e o balanceamento de xp_message_min_chars."""

    def _message(self, content, channel_id=999):
        message = Mock()
        message.author = Mock(bot=False, id=123, mention="@u")
        message.guild = Mock()
        message.channel = Mock(id=channel_id)
        message.content = content
        return message

    @pytest.mark.asyncio
    async def test_ignora_canal_log_none_sem_lancar_excecao(self, xp_cog):
        xp_cog.adicionar_xp = AsyncMock()
        xp_cog.bot.get_channel = Mock(return_value=None)
        message = self._message("mensagem de teste")

        await xp_cog.on_message(message)

        xp_cog.adicionar_xp.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ignora_mensagem_de_comando_com_exclamacao(self, xp_cog):
        xp_cog.adicionar_xp = AsyncMock()
        message = self._message("!xp")

        await xp_cog.on_message(message)

        xp_cog.adicionar_xp.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ignora_mensagem_de_comando_com_barra(self, xp_cog):
        xp_cog.adicionar_xp = AsyncMock()
        message = self._message("/xp")

        await xp_cog.on_message(message)

        xp_cog.adicionar_xp.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_respeita_min_chars_bloqueia_mensagem_curta(self, xp_cog):
        xp_cog.adicionar_xp = AsyncMock()
        xp_cog.bot.get_channel = Mock(return_value=None)
        xp_cog.xp_message_min_chars = 3
        message = self._message("hi")

        await xp_cog.on_message(message)

        xp_cog.adicionar_xp.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_respeita_min_chars_permite_mensagem_valida(self, xp_cog):
        xp_cog.adicionar_xp = AsyncMock()
        xp_cog.bot.get_channel = Mock(return_value=None)
        xp_cog.xp_message_min_chars = 3
        message = self._message("mensagem válida")

        await xp_cog.on_message(message)

        xp_cog.adicionar_xp.assert_awaited_once()


class TestVoiceXpAntiFarm:
    @pytest.mark.asyncio
    async def test_pula_usuario_deafened(self, xp_cog):
        xp_cog.bot.config = ServerConfig({"guild_id": 111, "afk_voice_channel_id": None})
        xp_cog.voice_xp_require_undeafened = True
        xp_cog.voice_xp_interval = 300
        xp_cog.adicionar_xp = AsyncMock()

        guild = Mock()
        member = Mock()
        member.voice.channel = Mock(id=555)
        member.voice.self_deaf = True
        member.voice.deaf = False
        guild.get_member = Mock(return_value=member)
        xp_cog.bot.get_guild = Mock(return_value=guild)
        xp_cog.bot.is_closed = Mock(side_effect=[False, True])

        xp_cog.voice_users = {"123": {"join_time": 9000, "last_xp_time": 9000}}

        with patch("cogs.progressao.xp.time.time", return_value=10000), \
             patch("cogs.progressao.xp.asyncio.sleep", new=AsyncMock()):
            await xp_cog.voice_xp_loop()

        xp_cog.adicionar_xp.assert_not_awaited()
        assert xp_cog.voice_users["123"]["last_xp_time"] == 9000  # não consumiu o tick

    @pytest.mark.asyncio
    async def test_credita_usuario_nao_deafened(self, xp_cog):
        xp_cog.bot.config = ServerConfig({"guild_id": 111, "afk_voice_channel_id": None})
        xp_cog.voice_xp_require_undeafened = True
        xp_cog.voice_xp_interval = 300
        xp_cog.voice_xp_amount = 15000
        xp_cog.adicionar_xp = AsyncMock()

        guild = Mock()
        member = Mock()
        member.voice.channel = Mock(id=555)
        member.voice.self_deaf = False
        member.voice.deaf = False
        guild.get_member = Mock(return_value=member)
        xp_cog.bot.get_guild = Mock(return_value=guild)
        xp_cog.bot.get_user = Mock(return_value=Mock(id=123))
        xp_cog.bot.is_closed = Mock(side_effect=[False, True])

        xp_cog.voice_users = {"123": {"join_time": 9000, "last_xp_time": 9000}}

        with patch("cogs.progressao.xp.time.time", return_value=10000), \
             patch("cogs.progressao.xp.asyncio.sleep", new=AsyncMock()):
            await xp_cog.voice_xp_loop()

        xp_cog.adicionar_xp.assert_awaited_once_with(123, 15000, "Voz no chat")
        assert xp_cog.voice_users["123"]["last_xp_time"] == 10000
