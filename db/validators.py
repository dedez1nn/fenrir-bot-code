"""Funções de validação de configuração por feature.

Puras: recebem um dict de server_config e retornam lista de erros.
Sem efeitos colaterais — usadas tanto pelas cogs (bot) quanto pela API.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List


def validate_tickets(cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    errors = []
    if not cfg.get("ticket_support_category_id") and not cfg.get("ticket_donation_category_id"):
        errors.append({
            "code": "CONFIG_MISSING_CATEGORY",
            "field": "ticket_support_category_id",
            "message": "Nenhuma categoria de ticket configurada.",
            "suggestion": "Configure ao menos uma categoria de suporte ou doação.",
        })
    if not cfg.get("ticket_staff_role_ids"):
        errors.append({
            "code": "CONFIG_MISSING_ROLE",
            "field": "ticket_staff_role_ids",
            "message": "Nenhum cargo de staff configurado para tickets.",
            "suggestion": "Adicione ao menos um cargo de staff.",
        })
    return errors


def validate_voice_creator(cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    errors = []
    if not cfg.get("voice_creator_channel_id"):
        errors.append({
            "code": "CONFIG_MISSING_CHANNEL",
            "field": "voice_creator_channel_id",
            "message": "Canal base de criação de voz não configurado.",
            "suggestion": "Configure um canal de voz como gatilho.",
        })
    return errors


def validate_member_logs(cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    errors = []
    if not cfg.get("member_join_log_channel_id"):
        errors.append({
            "code": "CONFIG_MISSING_CHANNEL",
            "field": "member_join_log_channel_id",
            "message": "Canal de log de entrada não configurado.",
            "suggestion": "Configure um canal para mensagens de boas-vindas.",
        })
    if not cfg.get("member_leave_log_channel_id"):
        errors.append({
            "code": "CONFIG_MISSING_CHANNEL",
            "field": "member_leave_log_channel_id",
            "message": "Canal de log de saída não configurado.",
            "suggestion": "Configure um canal para mensagens de saída.",
        })
    return errors


def validate_colors(cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    errors = []
    if not cfg.get("free_color_role_ids"):
        errors.append({
            "code": "CONFIG_MISSING_ROLE",
            "field": "free_color_role_ids",
            "message": "Nenhum cargo de cor gratuita configurado.",
            "suggestion": "Adicione ao menos um cargo de cor ao painel.",
        })
    return errors


def validate_premium(cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    errors = []
    if not os.getenv("ACCESS_TOKEN"):
        errors.append({
            "code": "CONFIG_MISSING_API_KEY",
            "field": "ACCESS_TOKEN",
            "message": "ACCESS_TOKEN do Mercado Pago não configurado.",
            "suggestion": "Defina ACCESS_TOKEN no arquivo .env.",
        })
    return errors


def validate_xp(cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    errors = []
    role_map = cfg.get("levelup_role_map") or {}
    for k, v in role_map.items():
        try:
            nivel = int(k)
            if nivel <= 0 or not isinstance(v, int) or v <= 0:
                raise ValueError
        except (ValueError, TypeError):
            errors.append({
                "code": "CONFIG_INVALID_ROLE_MAP",
                "field": "levelup_role_map",
                "message": f"Entrada inválida no mapa de cargos por nível: '{k}'.",
                "suggestion": "Use somente inteiros positivos como níveis e IDs de cargo.",
            })
            break
    return errors


def validate_adventures(cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    errors = []
    if not cfg.get("adventure_log_channel_id"):
        errors.append({
            "code": "CONFIG_MISSING_CHANNEL",
            "field": "adventure_log_channel_id",
            "message": "Canal de log de aventuras não configurado.",
            "suggestion": "Configure um canal para resultados de aventuras.",
        })
    return errors


def validate_guild_raids(cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    errors = []
    if not cfg.get("guild_raid_channel_id"):
        errors.append({
            "code": "CONFIG_MISSING_CHANNEL",
            "field": "guild_raid_channel_id",
            "message": "Canal de raids/alianças não configurado.",
            "suggestion": "Configure um canal para anúncios de raids.",
        })
    return errors


def validate_antispam(_cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    return []  # validação própria em AntispamConfig.from_dict()


def validate_antinuke(_cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    return []  # validação própria em AntinukeConfig.from_dict()


def validate_economy(cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    errors = []
    for field, min_val in [("coins_por_mensagem", 1), ("daily_coins", 1), ("xp_por_mensagem", 1)]:
        val = cfg.get(field)
        if val is not None and (not isinstance(val, int) or val < min_val):
            errors.append({
                "code": "CONFIG_INVALID_THRESHOLD",
                "field": field,
                "message": f"Valor inválido para {field}: {val}.",
                "suggestion": f"Use um inteiro ≥ {min_val}.",
            })
    return errors


def validate_guilds(_cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    return []  # storage verificado em runtime; sem pré-requisito de config


def validate_riot(_cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    if not os.getenv("RIOT_API_KEY"):
        return [{"code": "CONFIG_MISSING_API_KEY", "field": "RIOT_API_KEY",
                 "message": "RIOT_API_KEY não configurada.",
                 "suggestion": "Defina RIOT_API_KEY no arquivo .env."}]
    return []


def validate_steam(_cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    if not os.getenv("STEAM_API_KEY"):
        return [{"code": "CONFIG_MISSING_API_KEY", "field": "STEAM_API_KEY",
                 "message": "STEAM_API_KEY não configurada.",
                 "suggestion": "Defina STEAM_API_KEY no arquivo .env."}]
    return []


def validate_gnews(_cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    if not os.getenv("GNEWS_API_KEY"):
        return [{"code": "CONFIG_MISSING_API_KEY", "field": "GNEWS_API_KEY",
                 "message": "GNEWS_API_KEY não configurada.",
                 "suggestion": "Defina GNEWS_API_KEY no arquivo .env."}]
    return []


def validate_invite_blocker(_cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    return []  # sem pré-requisito de config além de permissão Manage Messages


def validate_auto_remove_bots(_cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    return []  # sem pré-requisito de config além de permissão Kick Members


def validate_status(cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    if not cfg.get("status_channel_id"):
        return [{"code": "CONFIG_MISSING_CHANNEL", "field": "status_channel_id",
                 "message": "Canal de status não configurado.",
                 "suggestion": "Configure um canal para o embed de status do bot."}]
    return []


VALIDATORS: Dict[str, Callable[[Dict[str, Any]], List[Dict[str, str]]]] = {
    "tickets":          validate_tickets,
    "voice_creator":    validate_voice_creator,
    "member_logs":      validate_member_logs,
    "colors":           validate_colors,
    "premium":          validate_premium,
    "xp":               validate_xp,
    "adventures":       validate_adventures,
    "guild_raids":      validate_guild_raids,
    "antispam":         validate_antispam,
    "antinuke":         validate_antinuke,
    "economy":          validate_economy,
    "guilds":           validate_guilds,
    "riot":             validate_riot,
    "steam":            validate_steam,
    "gnews":            validate_gnews,
    "invite_blocker":   validate_invite_blocker,
    "auto_remove_bots": validate_auto_remove_bots,
    "status":           validate_status,
}


def validate_all(cfg: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    """Roda todos os validadores e retorna {feature: [erros]}."""
    return {feature: fn(cfg) for feature, fn in VALIDATORS.items()}
