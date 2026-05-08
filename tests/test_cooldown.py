import json
import os
import time
from unittest.mock import Mock, patch

import pytest
from discord.ext import commands

from cogs.economia.cooldown import CooldownCog


@pytest.fixture
def bot():
    bot = Mock(spec=commands.Bot)
    bot.db = None  # força modo JSON nos testes
    return bot


@pytest.fixture
def cooldown_cog(bot, tmp_path):
    cog = CooldownCog(bot)
    cog.ARQUIVO_COOLDOWNS = str(tmp_path / "test_cooldowns.json")
    cog.cooldowns = {}
    cog.use_db = False  # garante modo JSON
    return cog


class TestCooldownCog:

    # ── carregar / salvar ────────────────────────────────────────────────────

    def test_carregar_dados_arquivo_existe(self, cooldown_cog, tmp_path):
        dados_teste = {"123": {"3": 1000, "6": 2000}}
        with open(cooldown_cog.ARQUIVO_COOLDOWNS, "w", encoding="utf-8") as f:
            json.dump(dados_teste, f)
        dados = cooldown_cog.carregar_dados()
        assert dados == dados_teste

    def test_carregar_dados_arquivo_nao_existe(self, cooldown_cog):
        dados = cooldown_cog.carregar_dados()
        assert dados == {}

    def test_salvar_dados(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"3": 1000}}
        cooldown_cog.salvar_dados()
        assert os.path.exists(cooldown_cog.ARQUIVO_COOLDOWNS)
        with open(cooldown_cog.ARQUIVO_COOLDOWNS, "r", encoding="utf-8") as f:
            assert json.load(f) == {"123": {"3": 1000}}

    # ── registrar_compra ─────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_registrar_compra_novo_usuario(self, cooldown_cog):
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 3)
        assert "123" in cooldown_cog.cooldowns
        assert "3" in cooldown_cog.cooldowns["123"]
        assert cooldown_cog.cooldowns["123"]["3"] == 1000 + 604800  # 7 dias

    @pytest.mark.asyncio
    async def test_registrar_compra_usuario_existente(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"5": 5000}}
        with patch("time.time", return_value=2000):
            await cooldown_cog.registrar_compra(123, 3)
        assert "5" in cooldown_cog.cooldowns["123"]
        assert cooldown_cog.cooldowns["123"]["3"] == 2000 + 604800

    @pytest.mark.asyncio
    async def test_registrar_compra_item_sem_cooldown_especifico(self, cooldown_cog):
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 99)
        assert cooldown_cog.cooldowns["123"]["99"] == 1000 + 86400

    @pytest.mark.asyncio
    async def test_registrar_compra_varios_itens(self, cooldown_cog):
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 3)
            await cooldown_cog.registrar_compra(123, 6)
            await cooldown_cog.registrar_compra(123, 12)
        assert len(cooldown_cog.cooldowns["123"]) == 3
        assert cooldown_cog.cooldowns["123"]["3"] == 1000 + 604800
        assert cooldown_cog.cooldowns["123"]["6"] == 1000 + 43200
        assert cooldown_cog.cooldowns["123"]["12"] == 1000 + 43200

    @pytest.mark.asyncio
    async def test_registrar_compra_com_cooldown_secs_explicito(self, cooldown_cog):
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 3, cooldown_secs=7200)
        assert cooldown_cog.cooldowns["123"]["3"] == 1000 + 7200

    # ── verificar_compra ─────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_verificar_compra_usuario_nao_existe(self, cooldown_cog):
        assert await cooldown_cog.verificar_compra(999, 3) is False

    @pytest.mark.asyncio
    async def test_verificar_compra_item_nao_comprado(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {}}
        assert await cooldown_cog.verificar_compra(123, 3) is False

    @pytest.mark.asyncio
    async def test_verificar_compra_cooldown_ativo(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"3": 2000}}
        with patch("time.time", return_value=1500):
            assert await cooldown_cog.verificar_compra(123, 3) is True

    @pytest.mark.asyncio
    async def test_verificar_compra_cooldown_expirado(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"3": 1000}}
        with patch("time.time", return_value=2000):
            assert await cooldown_cog.verificar_compra(123, 3) is False
            assert "123" not in cooldown_cog.cooldowns

    @pytest.mark.asyncio
    async def test_verificar_compra_expirado_remove_usuario_vazio(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"3": 1000}}
        with patch("time.time", return_value=2000):
            assert await cooldown_cog.verificar_compra(123, 3) is False
            assert "123" not in cooldown_cog.cooldowns

    # ── obter_tempo_restante ─────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_obter_tempo_restante_usuario_nao_existe(self, cooldown_cog):
        assert await cooldown_cog.obter_tempo_restante(999, 3) == 0

    @pytest.mark.asyncio
    async def test_obter_tempo_restante_item_nao_comprado(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {}}
        assert await cooldown_cog.obter_tempo_restante(123, 3) == 0

    @pytest.mark.asyncio
    async def test_obter_tempo_restante_ativo(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"3": 2000}}
        with patch("time.time", return_value=1500):
            assert await cooldown_cog.obter_tempo_restante(123, 3) == 500

    @pytest.mark.asyncio
    async def test_obter_tempo_restante_expirado(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"3": 1000}}
        with patch("time.time", return_value=2000):
            assert await cooldown_cog.obter_tempo_restante(123, 3) == 0

    @pytest.mark.asyncio
    async def test_obter_tempo_restante_com_valor_negativo(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"3": 1000}}
        with patch("time.time", return_value=2000):
            assert await cooldown_cog.obter_tempo_restante(123, 3) == 0

    # ── cooldowns por item ───────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_cooldown_roubo_coins(self, cooldown_cog):
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 3)
        assert cooldown_cog.cooldowns["123"]["3"] == 1000 + 604800

    @pytest.mark.asyncio
    async def test_cooldown_dobro_xp(self, cooldown_cog):
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 6)
        assert cooldown_cog.cooldowns["123"]["6"] == 1000 + 43200

    @pytest.mark.asyncio
    async def test_cooldown_renomear_canal(self, cooldown_cog):
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 10)
        assert cooldown_cog.cooldowns["123"]["10"] == 1000 + 86400

    @pytest.mark.asyncio
    async def test_cooldown_enquete(self, cooldown_cog):
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 12)
        assert cooldown_cog.cooldowns["123"]["12"] == 1000 + 43200

    @pytest.mark.asyncio
    async def test_cooldown_fixar_mensagem(self, cooldown_cog):
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 14)
        assert cooldown_cog.cooldowns["123"]["14"] == 1000 + 21600

    @pytest.mark.asyncio
    async def test_cooldown_cor_premium(self, cooldown_cog):
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 8)
        assert cooldown_cog.cooldowns["123"]["8"] == 1000 + 86400

    @pytest.mark.asyncio
    async def test_cooldown_bilheteria(self, cooldown_cog):
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 10)
        assert cooldown_cog.cooldowns["123"]["10"] == 1000 + 86400

    # ── integração ───────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_ciclo_completo_compra_expiracao(self, cooldown_cog):
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 3)
            assert await cooldown_cog.verificar_compra(123, 3) is True

        with patch("time.time", return_value=1500):
            assert await cooldown_cog.verificar_compra(123, 3) is True
            assert await cooldown_cog.obter_tempo_restante(123, 3) > 0

        with patch("time.time", return_value=1000 + 604800 + 1):
            assert await cooldown_cog.verificar_compra(123, 3) is False
            assert await cooldown_cog.obter_tempo_restante(123, 3) == 0

    @pytest.mark.asyncio
    async def test_multiplos_usuarios_independentes(self, cooldown_cog):
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 3)
            await cooldown_cog.registrar_compra(456, 3)
        assert cooldown_cog.cooldowns["123"]["3"] == cooldown_cog.cooldowns["456"]["3"]

    @pytest.mark.asyncio
    async def test_mesmo_usuario_itens_diferentes(self, cooldown_cog):
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 3)
            await cooldown_cog.registrar_compra(123, 6)
            assert await cooldown_cog.verificar_compra(123, 3) is True
            assert await cooldown_cog.verificar_compra(123, 6) is True

        with patch("time.time", return_value=1000 + 43200 + 1):
            assert await cooldown_cog.verificar_compra(123, 6) is False
            assert await cooldown_cog.verificar_compra(123, 3) is True
            assert "6" not in cooldown_cog.cooldowns["123"]
            assert "3" in cooldown_cog.cooldowns["123"]

        with patch("time.time", return_value=1000 + 604800 + 1):
            assert await cooldown_cog.verificar_compra(123, 3) is False
            assert "123" not in cooldown_cog.cooldowns

    @pytest.mark.asyncio
    async def test_verificar_compra_usuario_apos_expiracao_parcial(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"3": 1000, "6": 5000}}
        with patch("time.time", return_value=3000):
            assert await cooldown_cog.verificar_compra(123, 3) is False
            assert await cooldown_cog.verificar_compra(123, 6) is True
            assert "123" in cooldown_cog.cooldowns
            assert "3" not in cooldown_cog.cooldowns["123"]
            assert "6" in cooldown_cog.cooldowns["123"]

    # ── persistência ─────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_persistencia_dados(self, cooldown_cog, tmp_path):
        cooldown_cog.ARQUIVO_COOLDOWNS = str(tmp_path / "persist.json")
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 3)

        nova_cog = CooldownCog(cooldown_cog.bot)
        nova_cog.ARQUIVO_COOLDOWNS = cooldown_cog.ARQUIVO_COOLDOWNS
        nova_cog.use_db = False
        nova_cog.cooldowns = nova_cog.carregar_dados()
        assert "123" in nova_cog.cooldowns
        assert "3" in nova_cog.cooldowns["123"]

    # ── dict cooldowns_itens ─────────────────────────────────────────────────

    def test_cooldowns_itens_dict_correta(self, cooldown_cog):
        assert cooldown_cog.cooldowns_itens[3] == 604800
        assert cooldown_cog.cooldowns_itens[6] == 43200
        assert cooldown_cog.cooldowns_itens[10] == 86400
        assert cooldown_cog.cooldowns_itens[12] == 43200
        assert cooldown_cog.cooldowns_itens[14] == 21600
        assert cooldown_cog.cooldowns_itens[8] == 86400

    @pytest.mark.asyncio
    async def test_registrar_compra_item_id_inexistente(self, cooldown_cog):
        with patch("time.time", return_value=1000):
            await cooldown_cog.registrar_compra(123, 9999)
        assert cooldown_cog.cooldowns["123"]["9999"] == 1000 + 86400


@pytest.mark.asyncio
async def test_setup():
    from unittest.mock import AsyncMock, patch
    bot = AsyncMock()
    with patch("cogs.economia.cooldown.CooldownCog") as mock_cog:
        from cogs.economia.cooldown import setup as setup_func
        await setup_func(bot)
        mock_cog.assert_called_once_with(bot)
        bot.add_cog.assert_called_once()
