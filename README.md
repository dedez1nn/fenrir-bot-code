# Fenrir-BOT

Fenrir-BOT é um bot de Discord completo com sistema de economia própria, progressão de níveis, guilds com raids, loja integrada, suporte a pagamentos via Pix pelo Mercado Pago, integração com a Riot Games API, Steam API e feed de notícias via GNews.

## Funcionalidades

### Sistema de Economia e Progressão
- **FenrirCoins:** moeda própria usada na loja e em eventos.
- **Experiência e níveis:** XP acumulado por mensagens, tempo em voz e aventuras.
- **Multiplicadores:** premium (2x/4x/6x), dobro de XP por item e bônus de guild — empilhados de forma aditiva.
- **Daily:** recompensa diária com streak bônus.

### Guilds e Raids
- Criação e gerenciamento de guilds dentro do servidor.
- Sistema de raids entre guilds.
- XP de guild com multiplicador progressivo por nível.
- Rankings de guilds e usuários.

### Loja e Itens
- Loja com paginação, ordenada por preço.
- Compra de itens com FenrirCoins (cooldown por item).
- Itens com efeitos em XP, moedas, títulos personalizados e mais.

### Premium e Pagamentos
- Planos premium via Pix (Mercado Pago): Aventureiro, Lendário e Mítico.
- Ativação automática de cargo e recompensas após confirmação.
- Expiração automática de premium (30 dias).

### League of Legends e TFT (Riot Games API)
| Comando | Descrição |
|---------|-----------|
| `/lol-perfil <nick>` | Nível e ícone do invocador |
| `/lol-rank <nick>` | Solo/Duo e Flex com WR |
| `/lol-historico <nick>` | Últimas partidas com KDA e campeão |
| `/lol-maestria <nick>` | Top 5 campeões por maestria |
| `/lol-rotacao` | Campeões gratuitos da semana |
| `/lol-aovivo <nick>` | Partida em tempo real |
| `/lol-comparar <nick1> <nick2>` | Comparação de rank |
| `/tft-rank <nick>` | Rank TFT com WR |
| `/tft-historico <nick>` | Últimas partidas TFT com colocação |

### Steam
| Comando | Descrição |
|---------|-----------|
| `/steam-perfil <steamid>` | Perfil, status e país |
| `/steam-biblioteca <steamid>` | Total de jogos e horas |
| `/steam-recentes <steamid>` | Jogados nas últimas 2 semanas |
| `/steam-conquistas <steamid> <appid>` | % de conquistas em um jogo |
| `/steam-amigos <steamid>` | Lista de amigos online/offline |
| `/steam-bans <steamid>` | VAC ban e game bans |
| `/steam-jogo <appid>` | Detalhes e preço de um jogo |

### Notícias (GNews)
| Comando | Descrição |
|---------|-----------|
| `/noticias [categoria]` | Top headlines (9 categorias disponíveis) |
| `/buscar-noticias <query>` | Busca por assunto específico |

### Moderação e Automação
- Auto-remove de bots indesejados.
- Auto-delete de mensagens de convite para outros servidores.
- Sistema de tickets integrado.
- Administradores podem usar qualquer comando em qualquer canal.

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/dedez1nn/Fenrir-BOT-CODE.git
cd Fenrir-BOT-CODE
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure o `.env` com base no `.env.example`:
```bash
cp .env.example .env
```

Preencha as seguintes variáveis:

| Variável | Onde obter |
|----------|-----------|
| `TOKEN` | [Discord Developer Portal](https://discord.com/developers/applications) |
| `ACCESS_TOKEN` | [Mercado Pago Developers](https://www.mercadopago.com.br/developers) |
| `RIOT_API_KEY` | [Riot Developer Portal](https://developer.riotgames.com) — solicite uma Production Key para uso contínuo |
| `RIOT_REGION` | Padrão: `br1`. Outras opções: `na1`, `euw1`, `kr`, etc. |
| `STEAM_API_KEY` | [Steam Dev API Key](https://steamcommunity.com/dev/apikey) — instantânea e gratuita |
| `GNEWS_API_KEY` | [GNews.io](https://gnews.io) — plano gratuito: 100 req/dia |

## Uso

```bash
python main.py
```

Ou via Docker:
```bash
docker-compose up --build
```

## Testes

```bash
# Todos os testes
pytest

# Arquivo específico
pytest tests/test_aventura.py

# Teste específico
pytest tests/test_aventura.py::TestAventuraCog::test_init
```

## Contribuição

Contribuições são bem-vindas! Faça um fork do projeto, crie sua branch, implemente melhorias e abra um Pull Request.
