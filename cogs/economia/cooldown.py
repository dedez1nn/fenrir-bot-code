import time
import json
import os
from discord.ext import commands

class CooldownCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ARQUIVO_COOLDOWNS = "data/cooldowns_data.json"
        self.cooldowns = self.carregar_dados()

        self.cooldowns_itens = {
            3: 604800,   # 7 dias  - Roubo de Coins
            6: 43200,    # 12 horas - Dobro de Experiência
            8: 86400,    # 24 horas - Cores Premium (permanente, bloqueio de recompra)
            10: 86400,   # 24 horas - Bilheteria
            11: 86400,   # 24 horas - Cor Premium (temporária)
            12: 43200,   # 12 horas - Enquete
            13: 86400,   # 24 horas - Renomear Canal
            14: 21600,   # 6 horas  - Fixar Mensagem
        }

    def carregar_dados(self):
        if os.path.exists(self.ARQUIVO_COOLDOWNS):
            with open(self.ARQUIVO_COOLDOWNS, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def salvar_dados(self):
        with open(self.ARQUIVO_COOLDOWNS, "w", encoding="utf-8") as f:
            json.dump(self.cooldowns, f, indent=4)

    async def registrar_compra(self, user_id: int, item_id: int):
        user_id_str = str(user_id)
        item_id_str = str(item_id)
        
        if user_id_str not in self.cooldowns:
            self.cooldowns[user_id_str] = {}
        
        cooldown_duracao = self.cooldowns_itens.get(item_id, 86400)
        tempo_fim = time.time() + cooldown_duracao
        
        self.cooldowns[user_id_str][item_id_str] = tempo_fim
        self.salvar_dados()
        
        print(f"⏰ Cooldown registrado: User {user_id}, Item {item_id}, Duração: {cooldown_duracao}s")

    def verificar_compra(self, user_id: int, item_id: int) -> bool:
        user_id_str = str(user_id)
        item_id_str = str(item_id)
        
        if user_id_str not in self.cooldowns:
            return False
        
        if item_id_str not in self.cooldowns[user_id_str]:
            return False
        
        tempo_fim = self.cooldowns[user_id_str][item_id_str]
        if time.time() < tempo_fim:
            return True
        
        del self.cooldowns[user_id_str][item_id_str]
        if not self.cooldowns[user_id_str]:  
            del self.cooldowns[user_id_str]
        self.salvar_dados()
        return False

    def obter_tempo_restante(self, user_id: int, item_id: int) -> float:
        user_id_str = str(user_id)
        item_id_str = str(item_id)
        
        if user_id_str not in self.cooldowns:
            return 0
        
        if item_id_str not in self.cooldowns[user_id_str]:
            return 0
        
        tempo_fim = self.cooldowns[user_id_str][item_id_str]
        tempo_restante = tempo_fim - time.time()
        
        return max(0, tempo_restante) 

async def setup(bot: commands.Bot):
    await bot.add_cog(CooldownCog(bot))