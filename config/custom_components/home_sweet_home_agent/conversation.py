"""Conversation platform for the Home Sweet Home Agent integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import aiohttp
from homeassistant.components import conversation
from homeassistant.components.conversation import (
    AssistantContent,
    ChatLog,
    ConversationEntity,
    ConversationEntityFeature,
    ConversationInput,
    ConversationResult,
)
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HomeSweetHomeAgentConfigEntry
from .const import (
    AFFIRMATIVE_PHRASES,
    CONFIRM_PATH,
    CONFIRMATION_TTL_SECONDS,
    CONVERSATION_PATH,
    DECISION_APPROVE,
    DECISION_REJECT,
    NEGATIVE_PHRASES,
    STATUS_COMPLETED,
    STATUS_CONFIRMATION_REQUIRED,
    STATUS_FAILED,
)

_LOGGER = logging.getLogger(__name__)

_MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "cannot_connect": (
            "I can't reach the household assistant right now. "
            "Please try again later."
        ),
        "timeout": (
            "The household assistant took too long to respond. Please try again."
        ),
        "auth": (
            "The household assistant rejected the Home Assistant credentials. "
            "Please update the integration configuration."
        ),
        "unavailable": (
            "The household assistant is unavailable right now. "
            "Please try again later."
        ),
        "http_error": "The household assistant returned an unexpected response.",
        "malformed": "The household assistant returned an invalid response.",
        "failed": (
            "The household assistant could not complete that request "
            "({code}): {message}"
        ),
        "failed_no_message": (
            "The household assistant could not complete that request ({code})."
        ),
        "unexpected": (
            "An unexpected error occurred while talking to the household assistant."
        ),
        "empty_input": "Please say what you would like me to do.",
        "confirmation_ambiguous": "Please answer yes or no.",
        "confirmation_expired": (
            "That confirmation expired. Please repeat the request."
        ),
    },
    "pt": {
        "cannot_connect": (
            "Não consigo contactar o assistente da casa neste momento. "
            "Tente novamente mais tarde."
        ),
        "timeout": (
            "O assistente da casa demorou demasiado a responder. Tente novamente."
        ),
        "auth": (
            "O assistente da casa rejeitou as credenciais do Home Assistant. "
            "Atualize a configuração da integração."
        ),
        "unavailable": (
            "O assistente da casa está indisponível neste momento. "
            "Tente novamente mais tarde."
        ),
        "http_error": "O assistente da casa devolveu uma resposta inesperada.",
        "malformed": "O assistente da casa devolveu uma resposta inválida.",
        "failed": (
            "O assistente da casa não conseguiu concluir o pedido "
            "({code}): {message}"
        ),
        "failed_no_message": (
            "O assistente da casa não conseguiu concluir o pedido ({code})."
        ),
        "unexpected": (
            "Ocorreu um erro inesperado ao falar com o assistente da casa."
        ),
        "empty_input": "Diga o que gostaria que eu fizesse.",
        "confirmation_ambiguous": "Responda sim ou não.",
        "confirmation_expired": (
            "Essa confirmação expirou. Repita o pedido, por favor."
        ),
    },
}

_ERROR_KEYS = {
    "auth": "auth",
    "unavailable": "unavailable",
    "http_error": "http_error",
    "timeout": "timeout",
    "connection": "cannot_connect",
    "malformed": "malformed",
}


@dataclass(slots=True)
class PendingConfirmation:
    """One confirmation awaiting a yes/no follow-up."""

    token: str
    tool: str
    arguments_preview: Any
    expires_at: datetime
    language: str
    created_at: datetime


def _localized(language: str, key: str, **kwargs: Any) -> str:
    """Return a localized spoken message."""
    lang = "pt" if language.lower().startswith("pt") else "en"
    return _MESSAGES[lang][key].format(**kwargs)


def _normalize_phrase(text: str) -> str:
    """Normalize a follow-up phrase for yes/no matching."""
    cleaned = "".join(
        character if character.isalnum() or character.isspace() else " "
        for character in text.casefold()
    )
    return " ".join(cleaned.split())


def _decode_decision(text: str) -> str | None:
    """Return approve, reject, or None for an ambiguous follow-up."""
    normalized = _normalize_phrase(text)
    if not normalized:
        return None
    if normalized in AFFIRMATIVE_PHRASES:
        return DECISION_APPROVE
    if normalized in NEGATIVE_PHRASES:
        return DECISION_REJECT

    first = normalized.split()[0]
    if first in {"yes", "yeah", "yep", "sim"}:
        return DECISION_APPROVE
    if first in {"no", "nope", "nao", "não"}:
        return DECISION_REJECT

    for phrase in AFFIRMATIVE_PHRASES:
        if " " in phrase and (
            normalized.startswith(f"{phrase} ") or normalized.endswith(f" {phrase}")
        ):
            return DECISION_APPROVE
    for phrase in NEGATIVE_PHRASES:
        if " " in phrase and (
            normalized.startswith(f"{phrase} ") or normalized.endswith(f" {phrase}")
        ):
            return DECISION_REJECT
    return None


def _parse_expiry(value: Any) -> datetime:
    """Parse the agent confirmation expiry, falling back to the TTL."""
    now = dt_util.utcnow()
    parsed = dt_util.parse_datetime(value) if isinstance(value, str) else None
    if parsed is None:
        return now + timedelta(seconds=CONFIRMATION_TTL_SECONDS)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeSweetHomeAgentConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the conversation platform."""
    async_add_entities([HomeSweetHomeAgentConversationEntity(config_entry)])


class HomeSweetHomeAgentConversationEntity(ConversationEntity):
    """Conversation agent backed by the Home Sweet Home agent."""

    _attr_should_poll = False
    _attr_supported_features = ConversationEntityFeature.CONTROL
    _attr_supports_streaming = False

    def __init__(self, entry: HomeSweetHomeAgentConfigEntry) -> None:
        """Initialize the conversation entity."""
        self.entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_name = "Home Sweet Home Agent"
        self._pending: dict[str, PendingConfirmation] = {}

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return the supported languages."""
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """Register the entity as a conversation agent."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister the entity and drop transient confirmation state."""
        conversation.async_unset_agent(self.hass, self.entry)
        self._pending.clear()
        await super().async_will_remove_from_hass()

    async def _async_handle_message(
        self,
        user_input: ConversationInput,
        chat_log: ChatLog,
    ) -> ConversationResult:
        """Handle one user message."""
        conversation_id = user_input.conversation_id or chat_log.conversation_id
        try:
            return await self._async_process_message(
                user_input, chat_log, conversation_id
            )
        except Exception:
            _LOGGER.exception("Unexpected error processing a conversation request")
            return self._error_result(
                user_input,
                conversation_id,
                _localized(user_input.language, "unexpected"),
            )

    async def _async_process_message(
        self,
        user_input: ConversationInput,
        chat_log: ChatLog,
        conversation_id: str,
    ) -> ConversationResult:
        """Process text, including any pending confirmation."""
        text = user_input.text.strip()
        if not text:
            return self._error_result(
                user_input,
                conversation_id,
                _localized(user_input.language, "empty_input"),
            )

        pending = self._pending.get(conversation_id)
        if pending is not None:
            expires_at = pending.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= dt_util.utcnow():
                self._pending.pop(conversation_id, None)
                return self._error_result(
                    user_input,
                    conversation_id,
                    _localized(user_input.language, "confirmation_expired"),
                )

            decision = _decode_decision(text)
            if decision is None:
                return self._normal_result(
                    user_input,
                    conversation_id,
                    _localized(user_input.language, "confirmation_ambiguous"),
                    continue_conversation=True,
                )
            return await self._async_resolve_confirmation(
                user_input, chat_log, conversation_id, pending, decision
            )

        payload: dict[str, Any] = {"message": text}
        if conversation_id:
            payload["conversationId"] = conversation_id
        return await self._async_send(
            user_input, chat_log, conversation_id, CONVERSATION_PATH, payload
        )

    async def _async_resolve_confirmation(
        self,
        user_input: ConversationInput,
        chat_log: ChatLog,
        conversation_id: str,
        pending: PendingConfirmation,
        decision: str,
    ) -> ConversationResult:
        """Send a single-use confirmation decision."""
        self._pending.pop(conversation_id, None)
        payload = {
            "conversationId": conversation_id,
            "confirmationToken": pending.token,
            "decision": decision,
        }
        return await self._async_send(
            user_input, chat_log, conversation_id, CONFIRM_PATH, payload
        )

    async def _async_send(
        self,
        user_input: ConversationInput,
        chat_log: ChatLog,
        conversation_id: str,
        path: str,
        payload: dict[str, Any],
    ) -> ConversationResult:
        """Send a request to the agent and map the outcome."""
        data, error_key = await self._async_request(path, payload)
        if error_key is not None:
            return self._error_result(
                user_input,
                conversation_id,
                _localized(user_input.language, _ERROR_KEYS[error_key]),
            )
        return self._handle_agent_response(
            user_input, chat_log, conversation_id, data
        )

    async def _async_request(
        self, path: str, payload: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Perform one agent HTTP request."""
        runtime = self.entry.runtime_data
        try:
            async with runtime.session.post(
                f"{runtime.base_url}{path}",
                json=payload,
                headers={"Authorization": f"Bearer {runtime.token}"},
                timeout=runtime.conversation_timeout,
            ) as response:
                if response.status in (401, 403):
                    return None, "auth"
                if response.status >= 500:
                    return None, "unavailable"
                if response.status < 200 or response.status >= 300:
                    return None, "http_error"
                try:
                    data = await response.json(content_type=None)
                except ValueError:
                    return None, "malformed"
                if not isinstance(data, dict):
                    return None, "malformed"
                return data, None
        except TimeoutError:
            return None, "timeout"
        except aiohttp.ClientError:
            return None, "connection"
        except ValueError:
            return None, "malformed"

    def _handle_agent_response(
        self,
        user_input: ConversationInput,
        chat_log: ChatLog,
        conversation_id: str,
        data: dict[str, Any] | None,
    ) -> ConversationResult:
        """Map a parsed agent response to a conversation result."""
        if not isinstance(data, dict):
            return self._error_result(
                user_input,
                conversation_id,
                _localized(user_input.language, "malformed"),
            )

        status = data.get("status")
        if status == STATUS_COMPLETED:
            reply = data.get("reply")
            if not isinstance(reply, str) or not reply.strip():
                return self._error_result(
                    user_input,
                    conversation_id,
                    _localized(user_input.language, "malformed"),
                )
            chat_log.async_add_assistant_content_without_tools(
                AssistantContent(agent_id=user_input.agent_id, content=reply)
            )
            return self._normal_result(user_input, conversation_id, reply)

        if status == STATUS_FAILED:
            error = data.get("error")
            code = "unknown"
            message = ""
            if isinstance(error, dict):
                code = str(error.get("code") or "unknown")
                raw_message = error.get("message")
                if isinstance(raw_message, str):
                    message = raw_message
            if message:
                speech = _localized(
                    user_input.language, "failed", code=code, message=message
                )
            else:
                speech = _localized(
                    user_input.language, "failed_no_message", code=code
                )
            return self._error_result(user_input, conversation_id, speech)

        if status == STATUS_CONFIRMATION_REQUIRED:
            return self._handle_confirmation_required(
                user_input, conversation_id, data
            )

        return self._error_result(
            user_input,
            conversation_id,
            _localized(user_input.language, "unexpected"),
        )

    def _handle_confirmation_required(
        self,
        user_input: ConversationInput,
        conversation_id: str,
        data: dict[str, Any],
    ) -> ConversationResult:
        """Store a confirmation request and return the agent reply."""
        confirmation = data.get("confirmation")
        reply = data.get("reply")
        if (
            not isinstance(confirmation, dict)
            or not isinstance(reply, str)
            or not reply.strip()
        ):
            return self._error_result(
                user_input,
                conversation_id,
                _localized(user_input.language, "malformed"),
            )

        token = confirmation.get("token")
        if not isinstance(token, str) or not token:
            return self._error_result(
                user_input,
                conversation_id,
                _localized(user_input.language, "malformed"),
            )

        tool = confirmation.get("tool")
        self._pending[conversation_id] = PendingConfirmation(
            token=token,
            tool=tool if isinstance(tool, str) else "",
            arguments_preview=confirmation.get("argumentsPreview"),
            expires_at=_parse_expiry(confirmation.get("expiresAt")),
            language=user_input.language,
            created_at=dt_util.utcnow(),
        )
        return self._normal_result(
            user_input, conversation_id, reply, continue_conversation=True
        )

    def _normal_result(
        self,
        user_input: ConversationInput,
        conversation_id: str,
        speech: str,
        *,
        continue_conversation: bool = False,
    ) -> ConversationResult:
        """Build a normal conversation result."""
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(speech)
        return ConversationResult(
            response=response,
            conversation_id=conversation_id,
            continue_conversation=continue_conversation,
        )

    def _error_result(
        self,
        user_input: ConversationInput,
        conversation_id: str,
        speech: str,
    ) -> ConversationResult:
        """Build an error conversation result."""
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, speech)
        return ConversationResult(
            response=response,
            conversation_id=conversation_id,
            continue_conversation=False,
        )
