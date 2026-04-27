import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import time
import json
import os
from datetime import datetime, timezone
import discord
from discord.ext import commands

from cogs.cooldown import CooldownCog

@pytest.fixture
def bot():
    bot = Mock(spec=commands.Bot)
    return bot

@pytest.fixture
def cooldown_cog(bot, tmp_path):
    cog = CooldownCog(bot)
    # Usar diretório temporário para não interferir nos dados reais
    cog.ARQUIVO_COOLDOWNS = str(tmp_path / "test_cooldowns.json")
    cog.cooldowns = {}
    return cog

class TestCooldownCog:

    # ==================== TESTES DE CARREGAMENTO/SALVAMENTO ====================
    
    def test_carregar_dados_arquivo_existe(self, cooldown_cog, tmp_path):
        dados_teste = {"123": {"3": 1000, "6": 2000}}
        with open(cooldown_cog.ARQUIVO_COOLDOWNS, "w", encoding="utf-8") as f:
            json.dump(dados_teste, f)
        
        dados = cooldown_cog.carregar_dados()
        assert dados == dados_teste

    def test_carregar_dados_arquivo_nao_existe(self, cooldown_cog):
        dados = cooldown_cog.carregar_dados()
        assert dados == {}

    def test_salvar_dados(self, cooldown_cog, tmp_path):
        cooldown_cog.cooldowns = {"123": {"3": 1000}}
        cooldown_cog.salvar_dados()
        
        assert os.path.exists(cooldown_cog.ARQUIVO_COOLDOWNS)
        with open(cooldown_cog.ARQUIVO_COOLDOWNS, "r", encoding="utf-8") as f:
            dados = json.load(f)
            assert dados == {"123": {"3": 1000}}

    # ==================== TESTES DO REGISTRAR_COMPRA ====================
    
    def test_registrar_compra_novo_usuario(self, cooldown_cog):
        with patch('time.time', return_value=1000):
            cooldown_cog.registrar_compra(123, 3)
            
            assert "123" in cooldown_cog.cooldowns
            assert "3" in cooldown_cog.cooldowns["123"]
            # 7 dias = 604800 segundos
            assert cooldown_cog.cooldowns["123"]["3"] == 1000 + 604800

    def test_registrar_compra_usuario_existente(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"5": 5000}}
        
        with patch('time.time', return_value=2000):
            cooldown_cog.registrar_compra(123, 3)
            
            assert "5" in cooldown_cog.cooldowns["123"]
            assert "3" in cooldown_cog.cooldowns["123"]
            assert cooldown_cog.cooldowns["123"]["3"] == 2000 + 604800

    def test_registrar_compra_item_sem_cooldown_especifico(self, cooldown_cog):
        # Item 99 não está no dicionário, deve usar 86400 (24h) como padrão
        with patch('time.time', return_value=1000):
            cooldown_cog.registrar_compra(123, 99)
            
            assert cooldown_cog.cooldowns["123"]["99"] == 1000 + 86400

    def test_registrar_compra_varios_itens(self, cooldown_cog):
        with patch('time.time', return_value=1000):
            cooldown_cog.registrar_compra(123, 3)
            cooldown_cog.registrar_compra(123, 6)
            cooldown_cog.registrar_compra(123, 12)
            
            assert len(cooldown_cog.cooldowns["123"]) == 3
            assert cooldown_cog.cooldowns["123"]["3"] == 1000 + 604800
            assert cooldown_cog.cooldowns["123"]["6"] == 1000 + 43200
            assert cooldown_cog.cooldowns["123"]["12"] == 1000 + 43200

    # ==================== TESTES DO VERIFICAR_COMPRA ====================
    
    def test_verificar_compra_usuario_nao_existe(self, cooldown_cog):
        resultado = cooldown_cog.verificar_compra(999, 3)
        assert resultado is False

    def test_verificar_compra_item_nao_comprado(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {}}
        resultado = cooldown_cog.verificar_compra(123, 3)
        assert resultado is False

    def test_verificar_compra_cooldown_ativo(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"3": 2000}}
        with patch('time.time', return_value=1500):
            resultado = cooldown_cog.verificar_compra(123, 3)
            assert resultado is True

    def test_verificar_compra_cooldown_expirado(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"3": 1000}}
        with patch('time.time', return_value=2000):
            resultado = cooldown_cog.verificar_compra(123, 3)
            assert resultado is False
            assert "123" not in cooldown_cog.cooldowns

    def test_verificar_compra_expirado_remove_usuario_vazio(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"3": 1000}}
        with patch('time.time', return_value=2000):
            resultado = cooldown_cog.verificar_compra(123, 3)
            assert resultado is False
            assert "123" not in cooldown_cog.cooldowns

    # ==================== TESTES DO OBTER_TEMPO_RESTANTE ====================
    
    def test_obter_tempo_restante_usuario_nao_existe(self, cooldown_cog):
        resultado = cooldown_cog.obter_tempo_restante(999, 3)
        assert resultado == 0

    def test_obter_tempo_restante_item_nao_comprado(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {}}
        resultado = cooldown_cog.obter_tempo_restante(123, 3)
        assert resultado == 0

    def test_obter_tempo_restante_ativo(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"3": 2000}}
        with patch('time.time', return_value=1500):
            resultado = cooldown_cog.obter_tempo_restante(123, 3)
            assert resultado == 500

    def test_obter_tempo_restante_expirado(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"3": 1000}}
        with patch('time.time', return_value=2000):
            resultado = cooldown_cog.obter_tempo_restante(123, 3)
            assert resultado == 0

    # ==================== TESTES DOS DIFERENTES COOLDOWNS ====================
    
    def test_cooldown_roubo_coins(self, cooldown_cog):
        with patch('time.time', return_value=1000):
            cooldown_cog.registrar_compra(123, 3)
            assert cooldown_cog.cooldowns["123"]["3"] == 1000 + 604800

    def test_cooldown_dobro_xp(self, cooldown_cog):
        with patch('time.time', return_value=1000):
            cooldown_cog.registrar_compra(123, 6)
            assert cooldown_cog.cooldowns["123"]["6"] == 1000 + 43200

    def test_cooldown_renomear_canal(self, cooldown_cog):
        with patch('time.time', return_value=1000):
            cooldown_cog.registrar_compra(123, 10)
            assert cooldown_cog.cooldowns["123"]["10"] == 1000 + 86400

    def test_cooldown_enquete(self, cooldown_cog):
        with patch('time.time', return_value=1000):
            cooldown_cog.registrar_compra(123, 12)
            assert cooldown_cog.cooldowns["123"]["12"] == 1000 + 43200

    def test_cooldown_fixar_mensagem(self, cooldown_cog):
        with patch('time.time', return_value=1000):
            cooldown_cog.registrar_compra(123, 14)
            assert cooldown_cog.cooldowns["123"]["14"] == 1000 + 21600

    def test_cooldown_cor_premium(self, cooldown_cog):
        with patch('time.time', return_value=1000):
            cooldown_cog.registrar_compra(123, 8)
            assert cooldown_cog.cooldowns["123"]["8"] == 1000 + 86400

    def test_cooldown_bilheteria(self, cooldown_cog):
        with patch('time.time', return_value=1000):
            cooldown_cog.registrar_compra(123, 10)
            assert cooldown_cog.cooldowns["123"]["10"] == 1000 + 86400

    # ==================== TESTES DE INTEGRAÇÃO ====================
    
    def test_ciclo_completo_compra_expiracao(self, cooldown_cog):
        with patch('time.time', return_value=1000):
            cooldown_cog.registrar_compra(123, 3)
            assert cooldown_cog.verificar_compra(123, 3) is True
        
        with patch('time.time', return_value=1500):
            assert cooldown_cog.verificar_compra(123, 3) is True
            tempo = cooldown_cog.obter_tempo_restante(123, 3)
            assert tempo > 0
        
        with patch('time.time', return_value=1000 + 604800 + 1):
            assert cooldown_cog.verificar_compra(123, 3) is False
            assert cooldown_cog.obter_tempo_restante(123, 3) == 0

    def test_multiplos_usuarios_independentes(self, cooldown_cog):
        with patch('time.time', return_value=1000):
            cooldown_cog.registrar_compra(123, 3)
            cooldown_cog.registrar_compra(456, 3)
        
        assert "123" in cooldown_cog.cooldowns
        assert "456" in cooldown_cog.cooldowns
        assert cooldown_cog.cooldowns["123"]["3"] == cooldown_cog.cooldowns["456"]["3"]

    def test_mesmo_usuario_itens_diferentes(self, cooldown_cog):
        cooldown_cog.cooldowns = {}
        
        # Mantém o patch ativo durante todo o teste
        with patch('time.time', return_value=1000):
            cooldown_cog.registrar_compra(123, 3)
            cooldown_cog.registrar_compra(123, 6)
            
            # Verifica se estão ativos (ainda no mesmo tempo)
            assert cooldown_cog.verificar_compra(123, 3) is True
            assert cooldown_cog.verificar_compra(123, 6) is True
        
        # Avança o tempo para depois do cooldown do item 6 (43200s = 12h)
        with patch('time.time', return_value=1000 + 43200 + 1):
            assert cooldown_cog.verificar_compra(123, 6) is False
            assert cooldown_cog.verificar_compra(123, 3) is True
            assert "6" not in cooldown_cog.cooldowns["123"]
            assert "3" in cooldown_cog.cooldowns["123"]
        
        # Avança o tempo para depois do cooldown do item 3 também
        with patch('time.time', return_value=1000 + 604800 + 1):
            assert cooldown_cog.verificar_compra(123, 3) is False
            assert "123" not in cooldown_cog.cooldowns
    # ==================== TESTES DE PERSISTÊNCIA ====================
    
    def test_persistencia_dados(self, cooldown_cog, tmp_path):
        cooldown_cog.ARQUIVO_COOLDOWNS = str(tmp_path / "persist.json")
        
        with patch('time.time', return_value=1000):
            cooldown_cog.registrar_compra(123, 3)
        
        nova_cog = CooldownCog(cooldown_cog.bot)
        nova_cog.ARQUIVO_COOLDOWNS = cooldown_cog.ARQUIVO_COOLDOWNS
        nova_cog.cooldowns = nova_cog.carregar_dados()
        
        assert "123" in nova_cog.cooldowns
        assert "3" in nova_cog.cooldowns["123"]

    # ==================== TESTES DO DICIONÁRIO COOLDOWNS_ITENS ====================
    
    def test_cooldowns_itens_dict_correta(self, cooldown_cog):
        assert cooldown_cog.cooldowns_itens[3] == 604800
        assert cooldown_cog.cooldowns_itens[6] == 43200
        assert cooldown_cog.cooldowns_itens[10] == 86400
        assert cooldown_cog.cooldowns_itens[12] == 43200
        assert cooldown_cog.cooldowns_itens[14] == 21600
        assert cooldown_cog.cooldowns_itens[8] == 86400

    # ==================== TESTES DE EDGE CASES ====================
    
    def test_registrar_compra_item_id_inexistente(self, cooldown_cog):
        with patch('time.time', return_value=1000):
            cooldown_cog.registrar_compra(123, 9999)
            assert cooldown_cog.cooldowns["123"]["9999"] == 1000 + 86400

    def test_verificar_compra_usuario_apos_expiracao_parcial(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"3": 1000, "6": 5000}}
        with patch('time.time', return_value=3000):
            # Item 3 expirou, item 6 ainda ativo
            assert cooldown_cog.verificar_compra(123, 3) is False
            assert cooldown_cog.verificar_compra(123, 6) is True
            # Item 3 deve ser removido, usuário ainda existe (tem item 6)
            assert "123" in cooldown_cog.cooldowns
            assert "3" not in cooldown_cog.cooldowns["123"]
            assert "6" in cooldown_cog.cooldowns["123"]

    def test_obter_tempo_restante_com_valor_negativo(self, cooldown_cog):
        cooldown_cog.cooldowns = {"123": {"3": 1000}}
        with patch('time.time', return_value=2000):
            resultado = cooldown_cog.obter_tempo_restante(123, 3)
            assert resultado == 0  # Não pode retornar negativo

@pytest.mark.asyncio
async def test_setup():
    bot = AsyncMock()
    with patch('cogs.cooldown.CooldownCog') as mock_cog:
        from cogs.cooldown import setup as setup_func
        await setup_func(bot)
        mock_cog.assert_called_once_with(bot)
        bot.add_cog.assert_called_once()