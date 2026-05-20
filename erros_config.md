# errors_config.md

## Finalidade

Este documento é a fonte única de verdade para a futura migração das configurações do bot para um modelo gerenciável por painel web.

Escopo desta documentação:

- mapear dependências hardcoded
- inventariar todas as cogs
- definir regras de habilitação
- catalogar erros de configuração
- preparar a futura leitura e escrita via painel web

Este documento descreve o estado atual do código. Não propõe implementação imediata.

## 1. Superfícies de configuração já existentes

### 1.1 `server_config`

Já existe suporte parcial para:

- `commands_channel_id`
- `status_channel_id`
- `afk_voice_channel_id`
- `colors_channel_id`
- `pix_channel_id`
- `tickets_channel_id`
- `antispam_log_channel_id`
- `antinuke_log_channel_id`
- `coins_log_channel_id`
- `xp_log_channel_id`
- `levelup_channel_id`
- `admin_ping_ids`
- `levelup_role_map`
- `premium_prices`
- `premium_duration_days`
- `premium_multipliers`
- `daily_coins`
- `daily_streak_bonus`
- `coins_por_mensagem`
- `coins_por_voz`
- `xp_por_mensagem`
- `xp_por_voz`
- `voice_xp_interval_s`
- `bonus_coins_por_nivel`

### 1.2 `antispam_config`

Já existe suporte para:

- thresholds
- pontuação
- ladder de punição
- ativação/desativação
- blacklist
- canal de log
- listas/padrões do detector

### 1.3 `antinuke_config`

Já existe suporte para:

- thresholds de eventos
- severity escalation
- `enabled`
- `alert_only`
- whitelist
- admins pingados
- canal de log
- duração de lockdown

## 2. Mapeamento de dependências hardcoded

## 2.1 Configuração global do dono do bot

Esses itens fazem sentido como configuração global do produto, não por servidor cliente.

| Tipo | Local | Estado atual | Futuro esperado |
|---|---|---|---|
| Guild principal do bot | `main.py:27` | fallback fixo `1426202696955986022` | `global_config.primary_guild_id` ou `.env` sem fallback real |
| Guild principal do login OAuth | `api/routers/auth.py:37` | depende de `GUILD_ID` | `global_config.oauth_guild_id` |
| TTL do cache de config | `db/config.py:20` | `300s` | `global_config.server_config_ttl_s` |
| TTL da sessão JWT | `api/routers/auth.py:32` | `12h` | `global_config.admin_session_ttl_h` |
| Redirect URI OAuth | `api/routers/auth.py:29` | default local | `global_config.oauth_redirect_uri` |
| Pool do banco/API | `db/pool.py`, `api/db.py` | tamanhos e timeout fixos | `global_config.db_pool_*` |
| Seed inicial de IDs | `db/migrations/002_seed.sql` | acoplado ao servidor atual | seed por ambiente ou setup inicial guiado |
| Catálogo de planos premium | `cogs/economia/pix.py:28-42` | preços, cargos e recompensas fixos | `global_premium_catalog` |
| Política de branding | vários arquivos | nome, copyright, autor, versão fixos | `global_branding` |
| Assets CDN | vários arquivos | URLs de imagem hardcoded | `global_assets` |
| Lista de termos proibidos em título | `cogs/economia/compra.py:28` | lista fixa | `global_content_policy` |

## 2.2 Configuração por servidor do usuário

Esses itens precisam migrar para um modelo configurável por guild.

### 2.2.1 Canais, categorias e cargos

| Tipo | Local | Estado atual | Futuro esperado |
|---|---|---|---|
| Canal log de entrada | `cogs/moderacao/entrada.py:9` | ID fixo | `server_config.member_join_log_channel_id` |
| Canal de dúvidas | `cogs/moderacao/entrada.py:27` | ID fixo | `server_config.help_channel_id` |
| Canal log de saída | `cogs/moderacao/entrada.py:51` | ID fixo | `server_config.member_leave_log_channel_id` |
| Categorias de tickets | `cogs/moderacao/tickets.py:27-30` | IDs fixos | `server_config.ticket_category_*` |
| Cargos staff de ticket | `cogs/moderacao/tickets.py:49-53`, `303-320` | cargos fixos fundador/developer | `server_config.ticket_staff_role_ids` |
| Canal de logs de ticket | `cogs/moderacao/tickets.py:258-259` | ID fixo | `server_config.ticket_log_channel_id` |
| Canal criador de call | `cogs/moderacao/cria_canal.py:179` | ID fixo | `server_config.voice_creator_channel_id` |
| Canal de status | `cogs/interface/status.py:10` | ID fixo | `server_config.status_channel_id` |
| Canal de changelog | `cogs/interface/status.py:16` | ID fixo | `server_config.status_changelog_channel_id` |
| Cargos de cores gratuitas | `cogs/interface/enviar_cores.py:4-10` | IDs fixos | `server_config.free_color_role_ids` |
| Cargos de cores premium | `cogs/interface/enviar_cores.py:11-16`, `cogs/economia/compra.py:81-85` | IDs fixos duplicados | `server_config.premium_color_role_ids` |
| Cargo de item especial | `cogs/economia/compra.py:549` | ID fixo | `server_config.special_access_role_ids` |
| Canal log de aventuras | `cogs/progressao/aventurar.py:356,427,499` | ID fixo | `server_config.adventure_log_channel_id` |
| Canal de alianças/raids | `cogs/progressao/guild_2.py:777,877,923` | ID fixo | `server_config.guild_raid_channel_id` |
| Mapa de cargos por nível | `cogs/progressao/xp.py:336-349` | fallback fixo | `server_config.levelup_role_map` sem fallback por ID real |

### 2.2.2 Regras operacionais

| Tipo | Local | Estado atual | Futuro esperado |
|---|---|---|---|
| XP por mensagem | `cogs/progressao/xp.py:327` | default local | `server_config.xp_por_mensagem` |
| XP por vitória | `cogs/progressao/xp.py:328` | hardcoded | `server_config.xp_por_vitoria` |
| Coins por mensagem | `cogs/progressao/xp.py:329`, `cogs/economia/fenrir_coins.py:198` | valores divergentes | configuração única por servidor |
| Coins por voz | `cogs/progressao/xp.py:330`, `cogs/economia/fenrir_coins.py:200` | valores divergentes | configuração única por servidor |
| Coins por vitória | `cogs/progressao/xp.py:331` | hardcoded | `server_config.coins_por_vitoria` |
| Bônus de level up | `cogs/progressao/xp.py:332` | default local | `server_config.bonus_coins_por_nivel` |
| Cooldown de XP por mensagem | `cogs/progressao/xp.py:320` | `10s` | `server_config.xp_message_cooldown_s` |
| Cooldown de coins por mensagem | `cogs/economia/fenrir_coins.py:199` | `180s` | `server_config.coins_message_cooldown_s` |
| Daily e streak | `cogs/economia/fenrir_coins.py:201-202` | defaults locais | `server_config.daily_*` |
| Cooldowns de itens no modo JSON | `cogs/economia/cooldown.py:19-29` | tabela fixa por posição | usar apenas configuração por item no banco |
| XP base de guild | `cogs/progressao/guild.py:23` | hardcoded | `server_config.guild_xp_base` |
| Recompensas por nível de guild | `cogs/progressao/guild.py:24-40` | tabela fixa | `server_config.guild_level_rewards` ou tabela dedicada |
| Cooldown de raid | `cogs/progressao/guild.py:1437-1439` | `86400s` | `server_config.guild_raid_cooldown_s` |
| Aventura | `cogs/progressao/aventurar.py:18-36` | chances, recompensas e XP fixos | `server_config.adventure_*` ou tabela `adventure_rules` |

### 2.2.3 Moderação

| Tipo | Local | Estado atual | Futuro esperado |
|---|---|---|---|
| Antispam defaults | `cogs/antispam/config.py:8-93` | defaults no código | bootstrap + edição por servidor |
| Antinuke defaults | `cogs/antinuke/config.py:7-38` | defaults no código | bootstrap + edição por servidor |
| Cargo/role de blacklist | `cogs/antispam/punisher.py` | deriva por nome/config | validar por servidor antes de habilitar |

## 3. Inventário completo das cogs

### Convenção de leitura desta seção

- **Estado padrão atual**: como a cog entra em operação hoje
- **Dependências obrigatórias**: sem isso a cog não deveria ser habilitada no futuro
- **Configurações opcionais**: melhoram funcionamento, mas não precisam bloquear carga
- **Recursos externos**: APIs, banco, permissões Discord ou arquivos
- **Impacto sem configuração**: o que acontece hoje e o que o painel deve impedir amanhã

| Cog | Objetivo | Estado padrão atual | Dependências obrigatórias | Configurações opcionais | Recursos externos | Impacto sem configuração |
|---|---|---|---|---|---|---|
| `AntiNuke` | detectar raid, mass kick, mass ban, deleção de canais/cargos | carregada e ativa por padrão | `View Audit Log`, `Manage Channels`, guild alvo, config mínima válida | `log_channel_id`, `admin_ping_ids`, `whitelist_ids`, thresholds | audit log Discord, DB opcional | pode alertar sem agir; pode não conseguir slowmode/lockdown; sem log perde observabilidade |
| `AntiSpam` | detectar spam, links suspeitos, flood e aplicar punição | carregada e ativa por padrão | `Manage Messages`, config válida, storage funcional | canal de log, role blacklist, ladder custom, whitelist | DB/JSON, permissões Discord | sem permissões não remove mensagem; sem role blacklist perde parte da punição; sem log reduz rastreabilidade |
| `RiotCog` | comandos LoL/TFT | carregada por padrão | `RIOT_API_KEY` | região custom | Riot API, DDragon | comandos falham ou retornam erro quando a chave não existe |
| `SteamCog` | comandos Steam | carregada por padrão | `STEAM_API_KEY` | nenhuma | Steam API | comandos falham ou retornam perfil não encontrado/privado |
| `GNewsCog` | notícias e busca de notícias | carregada por padrão | `GNEWS_API_KEY` | idioma e limite podem virar config | GNews API | comandos falham ou atingem limite da API |
| `InviteBlocker` | bloquear convites de outros servidores | carregada e ativa | permissão `Manage Messages`, acesso a `fetch_invite` | mensagens custom de aviso | Discord API | sem permissão não apaga convite |
| `AutoRemoveBots` | expulsar bots não autorizados | carregada e ativa | permissão `Kick Members` | whitelist futura de bots | Discord API | pode expulsar bots desejados se não houver whitelist configurável |
| `FenrirCoins` | economia base, saldo, daily, ranking, transferências | carregada e ativa | `users` storage, guard channel funcional | canais de log, daily, streak, ganhos por ação | DB/JSON, imagens, aiohttp | sem config opera com defaults; sem log perde auditoria |
| `CooldownCog` | cooldowns de itens da loja | carregada e ativa | storage de cooldowns | catálogo de cooldowns por item | DB/JSON | em fallback JSON depende de mapeamento frágil por posição |
| `LojaCog` | exibir loja e CRUD de itens | carregada e ativa | storage de itens | canal de log de coins | DB/JSON | sem storage consistente a loja fica vazia ou divergente |
| `CompraCog` | executar efeitos da compra | carregada e ativa | `FenrirCoins`, `CooldownCog`, itens existentes | canais de log, cargos especiais, catálogo de cores | Discord roles/channels | várias compras falham parcialmente se o cargo/canal não existir |
| `ComandosLojaCog` | comandos desbloqueados por itens comprados | carregada e ativa | `CooldownCog`, `LojaCog`, `FenrirCoins` | durações, percentuais, canal de log | Discord permissions e canais | compra existe mas o efeito pode falhar se faltar permissão ou config |
| `PixCog` | premium automático via Mercado Pago | carregada e ativa | `ACCESS_TOKEN`, categoria de pagamento, catálogo premium válido, guild principal | canais de log, imagens, duração vinda do banco | Mercado Pago, Discord roles/channels, DB | premium pode cobrar sem conceder tudo; falhas em cargo/canal/log |
| `PremiumCog` | premium manual e expiração legada | carregada e ativa | storage de usuários | canal de log, catálogo premium | JSON, loops | conflita conceitualmente com `PixCog`; sem log perde rastreabilidade |
| `EnviarCores` | painel de escolha de cores | carregada e ativa | cargos de cor existentes, canal de cores | textos/branding | Discord roles | sem cargos o menu fica vazio ou inconsistente |
| `HelpCog` | catálogo de comandos | carregada e ativa | nenhuma crítica além do guard channel | páginas e descrições custom | Discord UI | pode exibir comandos que não funcionam se outras cogs estiverem mal configuradas |
| `StatusCog` | embed de status e changelog | carregada e ativa | canal de status e changelog válidos | branding, versão, assets | Discord channels | falha silenciosa ou posta no lugar errado |
| `AddRole` | adicionar/remover cargos | carregada e ativa | permissões `Manage Roles` do usuário e do bot | logs futuros | Discord roles | falha por hierarquia/permissão |
| `VoiceCreator` | criar e gerenciar calls privadas | carregada e ativa | canal base de voz configurado, permissão criar/mover/deletar canais | categoria, textos, cleanup interval | Discord voice channels | não cria salas ou gerencia incorretamente |
| `MemberLogs` | mensagem de entrada/saída | carregada e ativa | canais de join/leave válidos | canal de dúvidas, assets | Discord channels | onboarding incompleto ou mensagens perdidas |
| `ClearMessages` | purge de mensagens | carregada e ativa | permissão admin e `Manage Messages` | logs futuros | Discord permissions | comando falha imediatamente |
| `TicketCog` | criação, fechamento e transcript de tickets | carregada e ativa | categorias válidas, cargos staff, canal de logs, permissão criar canais | templates, branding | Discord channels/filesystem | tickets não abrem, não fecham corretamente ou perdem transcript |
| `AventuraCog` | aventuras, recompensas e expiração | carregada e ativa | storage de aventuras, `XPCog`, `FenrirCoins` | canal de log, regras de aventura | DB/JSON | jogador inicia aventura mas ganho/log pode falhar |
| `GuildSystem` | guilds, banco, ranking, convites e progressão | carregada e ativa | storage de guilds, `FenrirCoins` | regras de guild, recompensas, multiplicadores | DB/JSON | progressão fica acoplada ao default atual |
| `GuildAllianceRaidSystem` | alianças e raids | carregada e ativa | `GuildSystem`, `FenrirCoins`, `XPCog`, canal de raids | regras de raid, custos, timeouts | DB/JSON, Discord channels | raids/alianças falham por canal ausente e regras fixas |
| `XPCog` | XP, level up, ranking, voice XP, títulos e cargos por nível | carregada e ativa | storage de usuários, `FenrirCoins`, `GuildSystem`, mapa de cargos válido | canais de XP, AFK voice, regras de ganho | DB/JSON, Discord roles/channels | level up sem cargo, log perdido, valores inconsistentes |

## 4. Regras de habilitação e validação

## 4.1 Regra global futura

No painel web, nenhuma cog configurável deve ser marcada como “habilitada” se suas dependências obrigatórias estiverem ausentes.

Padrão desejado:

- **desabilitada por padrão** quando exigir configuração local
- **habilitável apenas após validação**
- **mensagem guiada de pendência** ao usuário

### Exemplo conceitual

Atual:

```python
self.bot.get_channel(ID_FIXO)
```

Futuro:

```python
if not servidor.config.ticket_log_channel_id:
    bloquear_habilitacao("Configure o canal de logs de ticket antes de ativar Tickets.")
```

## 4.2 Regras por domínio

### AntiSpam

Obrigatório:

- cog habilitada pelo painel
- permissões `Manage Messages`
- configuração válida de thresholds

Opcional:

- canal de log
- role de blacklist

Comportamento esperado:

- desabilitada por padrão
- se habilitar sem permissões → bloquear
- se habilitar sem role de blacklist → permitir apenas se a estratégia escolhida não exigir role

### AntiNuke

Obrigatório:

- cog habilitada pelo painel
- `View Audit Log`
- se `alert_only = false`, também precisa de permissão para agir

Opcional:

- canal de log
- pings administrativos

Comportamento esperado:

- desabilitada por padrão
- se faltar audit log → bloquear
- se modo ativo sem permissão para slowmode/lockdown → bloquear ou forçar `alert_only`

### Tickets

Obrigatório:

- categoria suporte e/ou doação
- staff roles ou política explícita de acesso
- canal de logs, se transcript for obrigatório
- permissão de criar canal

Comportamento esperado:

- não habilitar se não houver ao menos uma categoria funcional
- não habilitar se a política de visibilidade do staff ficar vazia

### XP

Obrigatório:

- valores válidos para XP/coins
- mapa de cargos por nível consistente, se “cargos por level” estiver habilitado

Opcional:

- canal de level up
- canal de log de XP
- AFK channel

Comportamento esperado:

- permitir XP sem cargos por nível
- bloquear apenas a subfunção “cargos por nível” se o mapa estiver inválido

### VoiceCreator

Obrigatório:

- canal base de voz
- permissão de criar, mover e deletar canais

Comportamento esperado:

- desabilitada por padrão
- bloquear se o canal base não existir

### Cores

Obrigatório:

- ao menos um cargo gratuito válido

Opcional:

- cargos premium

Comportamento esperado:

- painel de cores gratuitas pode habilitar sozinho
- recursos premium de cor exigem catálogo premium de cor válido

### Premium automático

Obrigatório:

- `ACCESS_TOKEN`
- catálogo premium válido
- cargos premium válidos, se o benefício envolver role
- categoria de pagamento válida

Opcional:

- canais de log
- assets visuais

Comportamento esperado:

- não habilitar cobrança se o plano não puder ser entregue

### APIs externas

Obrigatório:

- chave da API correspondente

Comportamento esperado:

- cog pode existir instalada, mas o painel deve permitir ativar/desativar por feature
- sem API key, deixar desabilitada

## 5. Catálogo de erros e mensagens

Esta seção define os erros de configuração que o painel deve exibir ao usuário.

| Código sugerido | Condição | Onde ocorre hoje | Mensagem esperada ao usuário | Sugestão de correção |
|---|---|---|---|---|
| `CONFIG_MISSING_CHANNEL` | canal obrigatório não configurado | tickets, entrada, status, aventura, XP, raids | “Este recurso exige um canal configurado antes de ser ativado.” | “Abra Configurações > Canais e selecione um canal válido.” |
| `CONFIG_MISSING_ROLE` | cargo obrigatório não configurado | premium, cores, level up, tickets | “Este recurso exige um cargo configurado.” | “Abra Configurações > Cargos e associe um cargo.” |
| `CONFIG_MISSING_CATEGORY` | categoria ausente | tickets, pix | “É necessário configurar uma categoria antes de ativar este recurso.” | “Defina a categoria no painel ou crie uma nova.” |
| `CONFIG_MISSING_API_KEY` | chave externa ausente | Riot, Steam, GNews, Mercado Pago | “A integração está desativada porque a chave de API não foi configurada.” | “Configure a chave em Integrações.” |
| `CONFIG_INVALID_ROLE_MAP` | mapa de cargos por nível incompleto ou inválido | XP | “O mapa de cargos por nível contém níveis ou cargos inválidos.” | “Revise a tabela de cargos por nível.” |
| `CONFIG_INVALID_PREMIUM_PLAN` | plano premium sem preço, role ou recompensa consistente | Pix, Premium manual | “O plano premium está incompleto e não pode ser ativado.” | “Revise preço, cargo e recompensas do plano.” |
| `CONFIG_INVALID_THRESHOLD` | threshold fora do intervalo aceito | antispam, antinuke | “Os thresholds configurados não são válidos.” | “Ajuste os valores para os limites suportados.” |
| `CONFIG_PERMISSION_BOT` | bot sem permissão necessária | tickets, addrole, limpar, antispam, antinuke, voice creator | “O bot não possui permissões suficientes para operar este recurso.” | “Ajuste as permissões do cargo do bot no Discord.” |
| `CONFIG_PERMISSION_USER` | usuário do servidor não tem permissão para ação | moderação/admin commands | “Você não possui permissão para executar esta ação.” | “Solicite acesso a um administrador.” |
| `CONFIG_INVALID_GUILD_CONTEXT` | recurso depende da guild principal ou de single-guild e foi usado fora do contexto | premium, OAuth, algumas lógicas de guild | “Este recurso ainda não suporta múltiplos servidores no estado atual.” | “Associe uma configuração específica por servidor antes de ativar.” |
| `CONFIG_STORAGE_UNAVAILABLE` | DB e fallback indisponíveis | várias cogs de economia/progressão | “Não foi possível acessar os dados necessários para este recurso.” | “Verifique a conexão com o banco ou a integridade do storage.” |
| `CONFIG_ASSET_UNAVAILABLE` | asset visual ausente/URL inválida | status, premium, aventura | “O recurso está ativo, mas um asset visual não foi encontrado.” | “Atualize a URL do asset no painel.” |

### 5.1 Mensagens atuais do código que já indicam ausência de configuração

Mensagens reais já existentes no código e que devem ser padronizadas no painel:

- “Categoria não configurada para este tipo de ticket!”
- “Categoria não encontrada!”
- “Canal não encontrado.”
- “Canal de logs não encontrado!”
- “Preciso da permissão **Gerenciar Canais** para criar o canal.”
- “Cargo não encontrado! Contate a administração.”
- “Sistema de coins indisponível no momento.”
- “Não foi possível obter as notícias.”
- “Perfil não encontrado. Verifique o SteamID64.”
- “A integração está indisponível” é a formulação sugerida para APIs faltantes

### 5.2 Erros futuros que o painel deve bloquear antes do runtime

- habilitar Tickets sem categorias
- habilitar XP com cargos por nível sem `levelup_role_map`
- habilitar Premium sem catálogo completo
- habilitar VoiceCreator sem canal base
- habilitar AntiNuke ativo sem permissões de ação
- habilitar AntiSpam sem permissões mínimas
- ativar cor premium sem cargos premium
- usar item de compra que depende de cargo/canal não configurado

## 6. Preparação para integração web

## 6.1 O que precisa ser exposto no painel

### Global do dono do bot

- catálogo premium
- recompensas premium
- branding
- assets
- integração Mercado Pago
- integrações Riot, Steam, GNews
- política de sessão/admin
- parâmetros de infraestrutura

### Por servidor

- canais
- categorias
- cargos
- toggles de features
- regras de XP/coins
- mapa de cargos por nível
- configuração de aventura
- configuração de guild/raid
- configuração de antispam
- configuração de antinuke
- mensagens/templates customizáveis

## 6.2 Estrutura conceitual de leitura/escrita

Leitura ideal:

1. carregar `global_config`
2. carregar `server_config`
3. carregar configs por feature
4. compor “effective config”
5. validar antes de habilitar

Escrita ideal:

1. receber patch do painel
2. validar esquema
3. validar referências do Discord
4. validar compatibilidade entre campos
5. persistir
6. emitir `pg_notify`
7. cog recarrega sem restart

## 6.3 Estrutura conceitual de entidades

Modelo sugerido:

- `global_config`
- `server_config`
- `feature_flags`
- `premium_catalog`
- `server_feature_config`
- `validation_state`

### Exemplo conceitual

```json
{
  "server_id": 123,
  "features": {
    "tickets": {
      "enabled": false,
      "config": {
        "support_category_id": 456,
        "donation_category_id": 789,
        "staff_role_ids": [111, 222],
        "log_channel_id": 333
      },
      "validation": {
        "is_valid": true,
        "missing": []
      }
    }
  }
}
```

## 6.4 Regras para impedir estados inválidos

O painel deve impedir:

- salvar IDs inexistentes
- salvar canais de tipo errado
- salvar cargos acima da hierarquia operável sem aviso
- ativar feature sem dependências obrigatórias
- salvar mapa de cargos por nível com níveis duplicados ou não numéricos
- ativar premium com cargo inexistente
- ativar integração sem chave de API
- ativar logs apontando para canal deletado
- manter referências duplicadas divergentes para o mesmo conceito

## 7. Inventário resumido do que o painel precisará validar por cog

| Cog | Validação mínima antes de habilitar |
|---|---|
| `AntiNuke` | thresholds válidos, permissões mínimas, modo coerente (`alert_only` ou permissão de ação) |
| `AntiSpam` | permissões mínimas, config válida, política de blacklist coerente |
| `RiotCog` | API key presente |
| `SteamCog` | API key presente |
| `GNewsCog` | API key presente |
| `InviteBlocker` | permissão `Manage Messages` |
| `AutoRemoveBots` | política de whitelist/allowlist definida, permissão `Kick Members` |
| `FenrirCoins` | canais de log opcionais, regras numéricas válidas |
| `CooldownCog` | itens consistentes no catálogo |
| `LojaCog` | storage válido |
| `CompraCog` | dependências cruzadas (`FenrirCoins`, `CooldownCog`, catálogo de efeitos) |
| `ComandosLojaCog` | itens compráveis e dependências de efeito válidas |
| `PixCog` | integração MP válida, categoria de pagamento, catálogo premium consistente |
| `PremiumCog` | decidir se permanece coexistindo com `PixCog` ou vira legado oculto |
| `EnviarCores` | pelo menos um cargo de cor configurado |
| `HelpCog` | nenhuma crítica, mas idealmente refletir feature flags reais |
| `StatusCog` | canal de status válido |
| `AddRole` | permissões do bot e do usuário |
| `VoiceCreator` | canal base e permissões de voz |
| `MemberLogs` | canais de entrada/saída válidos |
| `ClearMessages` | permissão `Manage Messages` |
| `TicketCog` | categorias, staff roles, política de transcript/log |
| `AventuraCog` | storage válido, `FenrirCoins` e `XPCog` presentes |
| `GuildSystem` | storage válido, regras de guild consistentes |
| `GuildAllianceRaidSystem` | storage válido, canal de raid, dependências cruzadas |
| `XPCog` | regras numéricas válidas, AFK channel opcional, cargos por nível consistentes |

## 8. Critérios de conclusão desta documentação

Esta documentação deve ser considerada completa porque descreve:

- todas as cogs carregadas pelo projeto
- os pontos hardcoded conhecidos
- dependências obrigatórias e opcionais
- efeitos da ausência de configuração
- regras de habilitação
- catálogo de erros e mensagens esperadas
- insumos necessários para o futuro painel web

## 9. Resumo executivo

O sistema atual opera com todas as cogs carregadas por padrão e com validação preventiva insuficiente. A base já possui uma boa fundação com `server_config`, `antispam_config` e `antinuke_config`, mas ainda existem dependências fortemente acopladas ao servidor original.

Para a próxima etapa do projeto, o painel web deve assumir três responsabilidades centrais:

1. armazenar configuração global e por servidor
2. validar dependências antes da habilitação
3. impedir estados inválidos antes que o erro aconteça em runtime

O foco prioritário da migração deve ser:

- canais/categorias/cargos hardcoded
- catálogo premium e recursos premium dependentes de cargo
- XP/coins/cooldowns com defaults divergentes
- tickets, aventuras, raids e voice creator
- qualquer cog cujo funcionamento atual dependa do servidor principal original
