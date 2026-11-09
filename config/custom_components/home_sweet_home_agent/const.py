"""Constants for the Home Sweet Home Agent integration."""

from __future__ import annotations

DOMAIN = "home_sweet_home_agent"

CONF_URL = "url"
CONF_TOKEN = "token"

CONVERSATION_PATH = "/conversation"
CONFIRM_PATH = "/confirm"
HEALTH_PATH = "/healthz"

DEFAULT_CONVERSATION_TIMEOUT = 90
DEFAULT_HEALTH_TIMEOUT = 10
CONFIRMATION_TTL_SECONDS = 120

STATUS_COMPLETED = "completed"
STATUS_CONFIRMATION_REQUIRED = "confirmation_required"
STATUS_FAILED = "failed"

DECISION_APPROVE = "approve"
DECISION_REJECT = "reject"

ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_AUTH = "invalid_auth"
ERROR_TIMEOUT = "timeout"
ERROR_UNKNOWN = "unknown"

AFFIRMATIVE_PHRASES = frozenset(
    {
        "yes",
        "yeah",
        "yep",
        "ok",
        "okay",
        "sure",
        "approve",
        "approved",
        "confirm",
        "confirmed",
        "do it",
        "go ahead",
        "please do",
        "sim",
        "claro",
        "pode",
        "pode fazer",
        "confirmo",
        "aprovado",
        "aprovo",
        "faz",
        "faca",
        "faça",
        "forca",
        "força",
        "esta bem",
        "está bem",
    }
)

NEGATIVE_PHRASES = frozenset(
    {
        "no",
        "nope",
        "no thanks",
        "cancel",
        "cancelled",
        "canceled",
        "reject",
        "stop",
        "nao",
        "não",
        "nao obrigado",
        "não obrigado",
        "cancela",
        "cancelar",
        "recusa",
        "recusar",
        "rejeita",
        "rejeitar",
        "para",
        "pára",
    }
)
