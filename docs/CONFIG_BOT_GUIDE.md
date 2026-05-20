# 🔧 Guia de Configuração do Bot com `/config-bot`

Este guia descreve como usar o novo sistema interativo de configuração do Fenrir.

## Comando Principal: `/config-bot`

Inicia um **wizard interativo** de 9 passos que guia você através de todas as configurações básicas do bot.

### Como usar:

```
/config-bot
```

O comando abrirá uma interface com:
- **9 passos de configuração** apresentados em embeds
- **Botões de navegação**: ◀️ Anterior | Próximo ▶️ | 💾 Salvar
- **Status visual** de cada configuração

### Passos do Wizard:

1. **📢 Canais de Log** — Commands, Status, Help, Antispam, Antinuke
2. **💰 Canais de Economia** — Pix, Loja, Coins Log, XP Log, Level Up
3. **🎫 Canais Especiais** — Tickets, Voice Creator, Adventure Log, Guild Raid
4. **💎 Preços Premium** — Aventureiro, Lendário, Mítico
5. **📈 Multiplicadores Premium** — XP/Coins por plano
6. **💰 Ganhos Diários** — Valores de coins para interações
7. **⭐ Ganhos de XP** — Valores de XP para interações
8. **🔔 Papéis de Notificação** — Roles para alertas
9. **✅ Resumo** — Revisar todas as configurações

---

## Comandos Específicos de Configuração

Para editar diretamente seções específicas sem passar por todo o wizard, use:

### `/config-canais-log`
Configura canais de log do bot.

**Parâmetros:**
- `commands` — Canal para logs de comandos
- `status` — Canal de status do bot
- `help` — Canal de ajuda
- `antispam` — Canal de log antispam
- `antinuke` — Canal de log antinuke

**Exemplo:**
```
/config-canais-log commands:#logs-bot status:#bot-status
```

---

### `/config-economia`
Configura ganhos de coins.

**Parâmetros:**
- `daily` — Coins do daily (ex: 10000)
- `bonus_daily` — Bonus de streak do daily (ex: 10000)
- `mensagem` — Coins por mensagem (ex: 5000)
- `voz` — Coins por minuto em voz (ex: 15000)
- `nivel` — Bonus de coins por level up (ex: 50000)

**Exemplo:**
```
/config-economia daily:10000 mensagem:5000 voz:15000
```

---

### `/config-xp`
Configura ganhos de XP.

**Parâmetros:**
- `mensagem` — XP por mensagem (ex: 5000)
- `voz` — XP por minuto em voz (ex: 15000)
- `intervalo` — Intervalo em segundos para dar XP em voz (ex: 300)

**Exemplo:**
```
/config-xp mensagem:5000 voz:15000 intervalo:300
```

---

### `/config-premium`
Configura preços dos planos premium em Pix.

**Parâmetros:**
- `aventureiro` — Preço em centavos (ex: 9900 = R$ 99)
- `lendario` — Preço em centavos
- `mitico` — Preço em centavos

**Exemplo:**
```
/config-premium aventureiro:9900 lendario:19900 mitico:29900
```

---

## Fluxo de Validação

Todos os comandos:
1. ✅ Verificam se o usuário é administrador
2. ✅ Verificam se o banco de dados está disponível
3. ✅ Atualizam `server_config` no PostgreSQL
4. ✅ **Invalidam cache** via `refresh_server_config()`
5. ✅ Emitem **NOTIFY** para sincronizar com o bot (`config:{guild_id}`)
6. ✅ Confirmam sucesso com embed verde

---

## Segurança

- Apenas **administradores** podem acessar estes comandos
- As alterações são **persistidas no PostgreSQL**
- A cache do bot é **invalidada automaticamente**
- As mudanças se **refletem em todos os processos** (via NOTIFY)

---

## Solução de Problemas

| Erro | Solução |
|------|---------|
| "Banco de dados não disponível" | Verifique se Postgres está rodando |
| "Você precisa ser administrador" | Peça a um admin para executar o comando |
| "Configuração não encontrada" | Verifique se a guild foi registrada no BD |
| Mudanças não refletem | Aguarde ~5 segundos para cache expirar |

---

## Arquitetura

Todos os dados são armazenados em `server_config` (tabela PostgreSQL):

- 🗄️ **Canais**: IDs BIGINT armazenados diretamente
- 💰 **Economia**: Valores INT64 para coins
- ⭐ **XP**: Valores INT64 para XP
- 💎 **Premium**: Preços em JSONB: `{"aventureiro": 9900, ...}`
- 🏷️ **Roles**: Arrays BIGINT: `{role_id1, role_id2, ...}`

Mudanças no banco disparam NOTIFY que o bot escuta em `_start_cache_listener()` (main.py).
