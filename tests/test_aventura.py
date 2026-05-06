import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands
import json
import os
import asyncio

# Importe correto do arquivo da cog
from cogs.progressao.aventurar import AventuraCog

@pytest.fixture
def bot():
    """Fixture do bot mockado"""
    bot = Mock(spec=commands.Bot)
    bot.get_cog = Mock()
    bot.get_user = Mock()  # Método síncrono
    bot.get_channel = Mock()
    bot.guilds = []  # Evita iteração em tests
    bot.add_view = Mock()
    return bot

@pytest.fixture
def aventura_cog(bot):
    """Fixture da AventuraCog com mocks - evitando iniciar tasks"""
    # Patch das tasks para não iniciarem durante os testes
    with patch.object(AventuraCog, 'verificar_aventuras_expiradas'), \
         patch.object(AventuraCog, 'verificar_aventuras_prontas'), \
         patch('asyncio.create_task'):
        
        cog = AventuraCog(bot)
        return cog

@pytest.fixture
def interaction():
    """Fixture do interaction mockado"""
    interaction = AsyncMock()
    interaction.user = Mock()
    interaction.user.id = 123456789
    interaction.user.mention = "@usuário"
    interaction.user.guild_permissions = Mock()
    interaction.user.guild_permissions.administrator = False
    interaction.channel = Mock()
    interaction.channel.id = 1426205118293868748  # Canal correto
    interaction.response = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction

@pytest.fixture
def mock_coins_cog():
    """Mock do sistema de coins"""
    mock = AsyncMock()
    mock.adicionar_coins = AsyncMock(return_value=True)
    return mock

@pytest.fixture
def mock_xp_cog():
    """Mock do sistema de XP"""
    mock = AsyncMock()
    mock.adicionar_xp = AsyncMock(return_value=True)
    return mock

@pytest.fixture
def aventura_data():
    """Fixture com dados de aventura"""
    return {
        "inicio": datetime.now(timezone.utc),
        "canal_id": 123456789,
        "situacao": {
            "nome": "Esqueletos na Masmorra",
            "descricao": "Teste",
            "imagem": "https://teste.com/image.png",
            "tipo": "combate"
        }
    }

class TestAventuraCog:
    
    def test_init(self, bot):
        """Teste de inicialização da cog"""
        with patch.object(AventuraCog, 'verificar_aventuras_expiradas'), \
             patch.object(AventuraCog, 'verificar_aventuras_prontas'), \
             patch('asyncio.create_task'):
            
            cog = AventuraCog(bot)
            
            assert cog.bot == bot
            assert cog.ARQUIVO_AVENTURAS == "data/aventuras_data.json"
            assert cog.COOLDOWN_HORAS == 0.001
            assert isinstance(cog.situacoes, list)
            assert len(cog.situacoes) == 3
    
    def test_carregar_dados_arquivo_existe(self, aventura_cog, tmp_path):
        """Teste carregar dados quando arquivo existe"""
        aventura_cog.ARQUIVO_AVENTURAS = str(tmp_path / "test_aventuras.json")
        
        dados_teste = {
            "123456": {
                "inicio": datetime.now(timezone.utc).isoformat(),
                "situacao": {"nome": "Teste"}
            }
        }
        
        with open(aventura_cog.ARQUIVO_AVENTURAS, "w", encoding="utf-8") as f:
            json.dump(dados_teste, f)
        
        dados = aventura_cog.carregar_dados()
        assert "123456" in dados
    
    def test_carregar_dados_arquivo_nao_existe(self, aventura_cog, tmp_path):
        """Teste carregar dados quando arquivo não existe"""
        aventura_cog.ARQUIVO_AVENTURAS = str(tmp_path / "inexistente.json")
        dados = aventura_cog.carregar_dados()
        assert dados == {}
    
    def test_salvar_dados(self, aventura_cog, tmp_path):
        """Teste salvar dados"""
        aventura_cog.ARQUIVO_AVENTURAS = str(tmp_path / "test_save.json")
        
        dados_teste = {
            "123456": {
                "inicio": datetime.now(timezone.utc),
                "situacao": {"nome": "Teste"}
            }
        }
        
        aventura_cog.salvar_dados(dados_teste)
        assert os.path.exists(aventura_cog.ARQUIVO_AVENTURAS)
        
        with open(aventura_cog.ARQUIVO_AVENTURAS, "r", encoding="utf-8") as f:
            dados_carregados = json.load(f)
            assert "123456" in dados_carregados
    
    def test_obter_aventura_usuario(self, aventura_cog, aventura_data):
        """Teste obter aventura de usuário específico"""
        with patch.object(aventura_cog, 'carregar_dados', return_value={"123456": aventura_data}):
            resultado = aventura_cog.obter_aventura_usuario(123456)
            assert resultado == aventura_data
    
    def test_obter_aventura_usuario_nao_existente(self, aventura_cog):
        """Teste obter aventura de usuário sem aventura"""
        with patch.object(aventura_cog, 'carregar_dados', return_value={}):
            resultado = aventura_cog.obter_aventura_usuario(999999)
            assert resultado is None
    
    def test_remover_aventura_usuario(self, aventura_cog, aventura_data):
        """Teste remover aventura de usuário"""
        with patch.object(aventura_cog, 'carregar_dados', return_value={"123456": aventura_data}), \
             patch.object(aventura_cog, 'salvar_dados') as mock_salvar:
            
            resultado = aventura_cog.remover_aventura_usuario(123456)
            assert resultado is True
            mock_salvar.assert_called_once()
    
    def test_remover_aventura_usuario_nao_existente(self, aventura_cog):
        """Teste remover aventura de usuário sem aventura"""
        with patch.object(aventura_cog, 'carregar_dados', return_value={}), \
             patch.object(aventura_cog, 'salvar_dados') as mock_salvar:
            
            resultado = aventura_cog.remover_aventura_usuario(999999)
            assert resultado is False
            mock_salvar.assert_not_called()
    
    def test_adicionar_aventura_usuario(self, aventura_cog, aventura_data):
        """Teste adicionar aventura para usuário"""
        with patch.object(aventura_cog, 'carregar_dados', return_value={}), \
             patch.object(aventura_cog, 'salvar_dados') as mock_salvar:
            
            aventura_cog.adicionar_aventura_usuario(123456, aventura_data)
            mock_salvar.assert_called_once()
    
    def test_obter_tempo_restante(self, aventura_cog):
        """Teste calcular tempo restante"""
        # Usar datetime.utcnow() para manter compatibilidade com a cog (que usa utcnow)
        inicio = datetime.utcnow() - timedelta(seconds=30)
        tempo_restante = aventura_cog.obter_tempo_restante(inicio)
        assert tempo_restante >= 0

    
    def test_obter_tempo_decorrido(self, aventura_cog):
        """Teste calcular tempo decorrido"""
        inicio = datetime.utcnow() - timedelta(seconds=30)
        tempo_decorrido = aventura_cog.obter_tempo_decorrido(inicio)
        assert tempo_decorrido >= 0
    
    def test_aventura_expirada(self, aventura_cog):
        """Teste verificar se aventura expirou"""
        with patch.object(aventura_cog, 'obter_tempo_restante', return_value=0):
            inicio = datetime.now(timezone.utc) - timedelta(hours=1)
            assert aventura_cog.aventura_expirada(inicio) is True
        
        with patch.object(aventura_cog, 'obter_tempo_restante', return_value=3600):
            inicio = datetime.now(timezone.utc) + timedelta(hours=1)
            assert aventura_cog.aventura_expirada(inicio) is False
    
    def test_aventura_pronta(self, aventura_cog):
        """Teste verificar se aventura está pronta"""
        with patch.object(aventura_cog, 'obter_tempo_restante', return_value=0):
            inicio = datetime.now(timezone.utc) - timedelta(hours=1)
            assert aventura_cog.aventura_pronta(inicio) is True
        
        with patch.object(aventura_cog, 'obter_tempo_restante', return_value=3600):
            inicio = datetime.now(timezone.utc) + timedelta(hours=1)
            assert aventura_cog.aventura_pronta(inicio) is False
    
    @pytest.mark.asyncio
    async def test_adicionar_xp_sucesso(self, aventura_cog, mock_xp_cog):
        """Teste adicionar XP com sucesso"""
        # Configura o mock do get_cog para retornar o AsyncMock
        aventura_cog.bot.get_cog = Mock(return_value=mock_xp_cog)
        
        # Mock do get_user (síncrono)
        mock_user = Mock()
        mock_user.mention = "@user"
        aventura_cog.bot.get_user.return_value = mock_user
        
        # Evita envio de mensagem para canal de log
        aventura_cog.bot.get_channel.return_value = None
        aventura_cog.bot.guilds = []  # evita iteração em guilds
        
        with patch('discord.Embed'), \
            patch('discord.utils.utcnow', return_value=datetime.utcnow()):
            resultado = await aventura_cog.adicionar_xp(123456, 1000, "Teste")
            assert resultado is True
            mock_xp_cog.adicionar_xp.assert_called_once_with(123456, 1000, "Teste")
    
    @pytest.mark.asyncio
    async def test_adicionar_xp_cog_nao_encontrada(self, aventura_cog):
        """Teste adicionar XP quando sistema não encontrado"""
        aventura_cog.bot.get_cog.return_value = None
        resultado = await aventura_cog.adicionar_xp(123456, 1000, "Teste")
        assert resultado is False
    
    def test_calcular_chance_vitoria(self, aventura_cog):
        """Teste calcular chance de vitória"""
        with patch('random.randint', return_value=50):
            situacao = {"dificuldade": "media"}
            chance = aventura_cog.calcular_chance_vitoria(situacao)
            assert chance == 50
    
    def test_calcular_chance_vitoria_alta(self, aventura_cog):
        """Teste calcular chance de vitória em dificuldade alta"""
        with patch('random.randint', return_value=30):
            situacao = {"dificuldade": "alta"}
            chance = aventura_cog.calcular_chance_vitoria(situacao)
            assert chance == 30
    
    def test_calcular_chance_machucado(self, aventura_cog):
        """Teste calcular chance de se machucar"""
        with patch('random.randint', return_value=50):
            situacao = {"dificuldade": "media"}
            chance = aventura_cog.calcular_chance_machucado(situacao)
            assert chance == 50
    
    def test_calcular_chance_machucado_alta(self, aventura_cog):
        """Teste calcular chance de se machucar em dificuldade alta"""
        with patch('random.randint', return_value=80):
            situacao = {"dificuldade": "alta"}
            chance = aventura_cog.calcular_chance_machucado(situacao)
            assert chance == 80
    
    def test_formatar_tempo(self, aventura_cog):
        """Teste formatação de tempo"""
        assert aventura_cog.formatar_tempo(3600) == "1h"
        assert aventura_cog.formatar_tempo(3660) == "1h 1m"
        assert aventura_cog.formatar_tempo(3661) == "1h 1m 1s"
        assert aventura_cog.formatar_tempo(120) == "2m"
        assert aventura_cog.formatar_tempo(65) == "1m 5s"
        assert aventura_cog.formatar_tempo(45) == "45s"
    
    def test_formatar_data_local(self, aventura_cog):
        """Teste formatação de data local"""
        data_teste = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
        resultado = aventura_cog.formatar_data_local(data_teste)
        assert "15 de janeiro de 2024" in resultado
    
    @pytest.mark.asyncio
    async def test_comando_aventura_canal_errado(self, aventura_cog, interaction):
        """Teste comando aventura em canal errado"""
        interaction.channel.id = 999999
        await aventura_cog.aventura.callback(aventura_cog, interaction)
        interaction.response.send_message.assert_called()
        assert "use esse **comando** apenas em" in interaction.response.send_message.call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_comando_aventura_nova(self, aventura_cog, interaction):
        """Teste iniciar nova aventura"""
        with patch.object(aventura_cog, 'obter_aventura_usuario', return_value=None), \
             patch.object(aventura_cog, 'adicionar_aventura_usuario') as mock_adicionar, \
             patch('random.choice', return_value=aventura_cog.situacoes[0]):
            
            await aventura_cog.aventura.callback(aventura_cog, interaction)
            mock_adicionar.assert_called_once()
            interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_comando_aventura_existente_pronta(self, aventura_cog, interaction, aventura_data):
        """Teste resgatar aventura pronta"""
        aventura_data["inicio"] = datetime.now(timezone.utc) - timedelta(hours=1)
        
        with patch.object(aventura_cog, 'obter_aventura_usuario', return_value=aventura_data), \
             patch.object(aventura_cog, 'aventura_pronta', return_value=True):
            
            await aventura_cog.aventura.callback(aventura_cog, interaction)
            interaction.response.send_message.assert_called_once()
            args = interaction.response.send_message.call_args[1]
            assert 'view' in args
    
    @pytest.mark.asyncio
    async def test_comando_aventura_status_canal_errado(self, aventura_cog, interaction):
        """Teste aventura_status em canal errado"""
        interaction.channel.id = 999999
        await aventura_cog.aventura_status.callback(aventura_cog, interaction)
        interaction.response.send_message.assert_called()
        assert "use esse **comando** apenas em" in interaction.response.send_message.call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_comando_aventura_status_sem_aventura(self, aventura_cog, interaction):
        """Teste verificar status sem aventura"""
        with patch.object(aventura_cog, 'obter_aventura_usuario', return_value=None):
            await aventura_cog.aventura_status.callback(aventura_cog, interaction)
            interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_aventura_view_interaction_check(self, aventura_cog):
        """Teste verificação de interação da view"""
        view = aventura_cog.AventuraView(aventura_cog, 123456, None, aventura_cog.situacoes[0])
        interaction = AsyncMock()
        interaction.user.id = 123456
        interaction.response.send_message = AsyncMock()
        
        with patch.object(aventura_cog, 'obter_aventura_usuario', 
                          return_value={"inicio": datetime.now(timezone.utc)}), \
             patch.object(aventura_cog, 'aventura_pronta', return_value=True):
            resultado = await view.interaction_check(interaction)
            assert resultado is True
    
    @pytest.mark.asyncio
    async def test_aventura_view_interaction_check_usuario_errado(self, aventura_cog):
        """Teste verificação de interação com usuário errado"""
        view = aventura_cog.AventuraView(aventura_cog, 123456, None, aventura_cog.situacoes[0])
        interaction = AsyncMock()
        interaction.user.id = 999999
        interaction.response.send_message = AsyncMock()
        
        resultado = await view.interaction_check(interaction)
        assert resultado is False
        interaction.response.send_message.assert_called_with("❌ Esta aventura não é sua!", ephemeral=True)

@pytest.mark.asyncio
async def test_setup():
    """Teste função setup"""
    bot = AsyncMock()
    with patch('cogs.progressao.aventurar.AventuraCog') as mock_cog:
        from cogs.progressao.aventurar import setup as setup_func
        await setup_func(bot)
        mock_cog.assert_called_once_with(bot)
        bot.add_cog.assert_called_once()