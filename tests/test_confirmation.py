"""Confirmation flow tests for the Home Sweet Home Agent integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.home_sweet_home_agent.const import (
    DECISION_APPROVE,
    DECISION_REJECT,
)
from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

CONFIRMATION_TOKEN = "confirmation-token-1"


async def _setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the config entry and wait for the platform."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _converse(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    text: str,
    conversation_id: str | None = None,
) -> conversation.ConversationResult:
    """Send one request through the conversation agent."""
    return await conversation.async_converse(
        hass,
        text,
        conversation_id,
        Context(),
        language="en",
        agent_id=entry.entry_id,
    )


def _speech(result: conversation.ConversationResult) -> str:
    """Return the plain speech from a result."""
    return result.response.speech["plain"]["speech"]


def _confirmation_payload(expires_in: int = 60) -> dict:
    """Return a confirmation_required response payload."""
    expires = datetime.now(UTC) + timedelta(seconds=expires_in)
    return {
        "status": "confirmation_required",
        "reply": "Turning off the heater will make the room cold. Confirm?",
        "confirmation": {
            "token": CONFIRMATION_TOKEN,
            "tool": "set_heater_power",
            "argumentsPreview": {"power": "off"},
            "expiresAt": expires.isoformat(),
        },
    }


def _confirm_calls(aioclient_mock) -> list:
    """Return the /confirm calls made by the integration."""
    return [
        call
        for call in aioclient_mock.mock_calls
        if str(call[1]).endswith("/confirm")
    ]


async def _request_confirmation(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    aioclient_mock,
    agent_url: str,
    expires_in: int = 60,
) -> conversation.ConversationResult:
    """Request an action that needs confirmation."""
    aioclient_mock.post(
        f"{agent_url}/conversation", json=_confirmation_payload(expires_in)
    )
    return await _converse(hass, entry, "Turn off the heater")


async def test_approval_executes_once(
    hass: HomeAssistant,
    aioclient_mock,
    mock_agent_entry: MockConfigEntry,
    agent_url: str,
) -> None:
    """An approval sends exactly one approve decision."""
    await _setup_entry(hass, mock_agent_entry)

    first = await _request_confirmation(
        hass, mock_agent_entry, aioclient_mock, agent_url
    )
    assert first.continue_conversation is True
    assert _speech(first) == (
        "Turning off the heater will make the room cold. Confirm?"
    )

    aioclient_mock.post(
        f"{agent_url}/confirm",
        json={"status": "completed", "reply": "The heater is now off."},
    )
    approval = await _converse(
        hass, mock_agent_entry, "yes", first.conversation_id
    )

    assert _speech(approval) == "The heater is now off."
    confirm_calls = _confirm_calls(aioclient_mock)
    assert len(confirm_calls) == 1
    _method, _url, data, headers = confirm_calls[0]
    assert data == {
        "conversationId": first.conversation_id,
        "confirmationToken": CONFIRMATION_TOKEN,
        "decision": DECISION_APPROVE,
    }
    assert headers["Authorization"].startswith("Bearer ")

    replay = await _converse(
        hass, mock_agent_entry, "yes", first.conversation_id
    )
    assert replay.response.response_type.name in {"ACTION_DONE", "ERROR"}
    assert len(_confirm_calls(aioclient_mock)) == 1


async def test_rejection_executes_nothing(
    hass: HomeAssistant,
    aioclient_mock,
    mock_agent_entry: MockConfigEntry,
    agent_url: str,
) -> None:
    """A rejection sends one reject decision and reports cancellation."""
    await _setup_entry(hass, mock_agent_entry)
    first = await _request_confirmation(
        hass, mock_agent_entry, aioclient_mock, agent_url
    )

    aioclient_mock.post(
        f"{agent_url}/confirm",
        json={"status": "completed", "reply": "The request was cancelled."},
    )
    rejection = await _converse(
        hass, mock_agent_entry, "no", first.conversation_id
    )

    assert _speech(rejection) == "The request was cancelled."
    confirm_calls = _confirm_calls(aioclient_mock)
    assert len(confirm_calls) == 1
    assert confirm_calls[0][2]["decision"] == DECISION_REJECT


async def test_expired_confirmation_never_sends_approve(
    hass: HomeAssistant,
    aioclient_mock,
    mock_agent_entry: MockConfigEntry,
    agent_url: str,
) -> None:
    """A locally expired confirmation is refused without calling /confirm."""
    await _setup_entry(hass, mock_agent_entry)
    first = await _request_confirmation(
        hass, mock_agent_entry, aioclient_mock, agent_url, expires_in=-1
    )
    assert first.continue_conversation is True

    expired = await _converse(
        hass, mock_agent_entry, "yes", first.conversation_id
    )

    assert expired.response.response_type.name == "ERROR"
    assert "expired" in _speech(expired)
    assert _confirm_calls(aioclient_mock) == []
    assert aioclient_mock.call_count == 1


async def test_ambiguous_follow_up_keeps_confirmation_pending(
    hass: HomeAssistant,
    aioclient_mock,
    mock_agent_entry: MockConfigEntry,
    agent_url: str,
) -> None:
    """An ambiguous answer asks again and can then be approved."""
    await _setup_entry(hass, mock_agent_entry)
    first = await _request_confirmation(
        hass, mock_agent_entry, aioclient_mock, agent_url
    )

    ambiguous = await _converse(
        hass, mock_agent_entry, "maybe", first.conversation_id
    )
    assert _speech(ambiguous) == "Please answer yes or no."
    assert ambiguous.continue_conversation is True
    assert _confirm_calls(aioclient_mock) == []

    aioclient_mock.post(
        f"{agent_url}/confirm",
        json={"status": "completed", "reply": "The heater is now off."},
    )
    approval = await _converse(
        hass, mock_agent_entry, "yes please", first.conversation_id
    )
    assert _speech(approval) == "The heater is now off."
    assert len(_confirm_calls(aioclient_mock)) == 1


async def test_agent_side_expired_token_is_an_error(
    hass: HomeAssistant,
    aioclient_mock,
    mock_agent_entry: MockConfigEntry,
    agent_url: str,
) -> None:
    """An agent-reported expired confirmation is never treated as success."""
    await _setup_entry(hass, mock_agent_entry)
    first = await _request_confirmation(
        hass, mock_agent_entry, aioclient_mock, agent_url
    )

    aioclient_mock.post(
        f"{agent_url}/confirm",
        json={
            "status": "failed",
            "error": {
                "code": "confirmation_expired",
                "message": "The confirmation token has expired.",
            },
        },
    )
    result = await _converse(
        hass, mock_agent_entry, "yes", first.conversation_id
    )

    assert result.response.response_type.name == "ERROR"
    assert "confirmation_expired" in _speech(result)
    assert len(_confirm_calls(aioclient_mock)) == 1


async def test_portuguese_yes_is_recognized(
    hass: HomeAssistant,
    aioclient_mock,
    mock_agent_entry: MockConfigEntry,
    agent_url: str,
) -> None:
    """Portuguese confirmation words resolve the pending action."""
    await _setup_entry(hass, mock_agent_entry)

    aioclient_mock.post(
        f"{agent_url}/conversation", json=_confirmation_payload()
    )
    first = await conversation.async_converse(
        hass,
        "Desliga o aquecedor",
        None,
        Context(),
        language="pt-PT",
        agent_id=mock_agent_entry.entry_id,
    )

    aioclient_mock.post(
        f"{agent_url}/confirm",
        json={"status": "completed", "reply": "O aquecedor está desligado."},
    )
    approval = await conversation.async_converse(
        hass,
        "sim",
        first.conversation_id,
        Context(),
        language="pt-PT",
        agent_id=mock_agent_entry.entry_id,
    )

    assert _speech(approval) == "O aquecedor está desligado."
    assert _confirm_calls(aioclient_mock)[0][2]["decision"] == DECISION_APPROVE
