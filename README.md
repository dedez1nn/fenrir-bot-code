# Fenrir Security — Bot de Moderação

Bot de segurança e moderação para Discord, construído com `discord.py` (slash commands via `app_commands`). Roda de forma independente no [Discloud](https://discloud.com) como unidade dedicada a proteção do servidor.

---

## Funcionalidades

### Anti-Spam (`cogs/antispam/`)
Monitoramento em tempo real de mensagens com pontuação cumulativa, decaimento por tempo e punições progressivas.

**Categorias detectadas**
- Flood (N mensagens por janela de tempo)
- Mensagens duplicadas (similaridade ≥ 92% via SequenceMatcher)
- Mass mention / @everyone abuse
- Links suspeitos (encurtadores, grabify, iplogger — com ou sem `https://`)
- Domínios nus (`bit.ly/algo`, `imgur.com/path`)
- E-mails sem prefixo (`usuario@dominio.tld`)
- Phishing por keyword (free nitro, steam gift, domínios falsos)
- Spam promocional / publicitário
- Link bait (frase de isca + URL)
- Caracteres invisíveis / zero-width (anti-evasão unicode)
- Caps excessivo, flood de emojis, flood de newlines
- Edit-spam

**Punições (ladder configurável)**

| Score | Ação padrão |
|-------|-------------|
| 5 | Aviso (DM) |
| 10 | Timeout 5 min |
| 20 | Timeout 10 min |
| 35 | Kick |
| 50 | Ban |

**Cargo Blacklist:** aplicado automaticamente em score ≥ 25, removido em score ≤ 8.

**Comandos** (requer `Gerenciar Servidor`)
```
/antispam toggle on|off
/antispam status
/antispam reset @user
/antispam whitelist @user add|remove
/antispam threshold score action
/antispam canal_log [#canal]
/infractions @user
/blacklist add|remove @user
```

---

### Anti-Nuke (`cogs/antinuke/`)
Proteção contra ataques em escala: raids, deleção em massa de canais/roles, mass ban/kick.

**Eventos monitorados**

| Evento | Threshold padrão |
|--------|-----------------|
| Joins em massa | 15 em 30s |
| Deleção de canais | 3 em 10s |
| Deleção de roles | 3 em 10s |
| Mass ban | 5 em 10s |
| Mass kick | 5 em 10s |
| Conta nova (< 7 dias) | por join |

**Escala de severidade** (decai 1/min sem eventos)

| Severidade | Ação |
|------------|------|
| 1 | Log no canal de auditoria |
| 2 | Log + ping nos admins configurados |
| 3 | Log + slowmode 30s em todos os canais |
| 4 | Log + lockdown completo (auto-unlock configurável) |

Por padrão opera em **modo alert-only** — registra e alerta sem agir automaticamente.

**Comandos** (requer `Administrador`)
```
/antinuke toggle on|off
/antinuke modo alert|ativo
/antinuke status
/antinuke whitelist @user add|remove
/antinuke ping_admin @user add|remove
/antinuke canal_log #canal
/antinuke lockdown [motivo]
/antinuke unlock
/antinuke reset_severidade
```

---

### Comando de Emergência
```
/emergencia
```
Desativa **Anti-Spam e Anti-Nuke simultaneamente**. Requer `Administrador`. Use quando os sistemas estiverem causando falsos positivos em larga escala. Para reativar: `/antispam toggle on` e `/antinuke toggle on`.

---

### Outros módulos

| Cog | Função |
|-----|--------|
| `security.py` | Kick automático de bots não autorizados no join |
| `block_inv.py` | Remove convites de servidores externos |
| `status.py` | Embed de status online + `/manutencao` |

---

## Instalação

```bash
git clone <repo>
cd fenrir
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # adicione TOKEN=<seu token>
python main.py
```

## Configuração inicial

```
/antispam canal_log          # cria #antispam-logs com permissões restritas
/antinuke canal_log #canal   # define canal de log do antinuke
/antinuke ping_admin @voce add
/antispam status             # confirma thresholds
/antinuke status
```

Crie o cargo **`Blacklist`** manualmente no servidor e posicione-o abaixo do cargo do bot na hierarquia.

## Variáveis de ambiente

```
TOKEN=<Discord bot token>
```

## Deploy (Discloud)

```
TYPE=bot
MAIN=main.py
NAME=Fenrir Security
RAM=500
AUTORESTART=false
```
