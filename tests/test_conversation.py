"""Conversation flow tests for the Home Sweet Home Agent integration."""

from __future__ import annotations

import aiohttp
import pytest
from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def _setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the config entry and wait for the platform."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _converse(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    text: str,
    conversation_id: str | None = None,
    language: str = "en",
) -> conversation.ConversationResult:
    """Send one request through the conversation agent."""
    return await conversation.async_converse(
        hass,
        text,
        conversation_id,
        Context(),
        language=language,
        agent_id=entry.entry_id,
    )


def _speech(result: conversation.ConversationResult) -> str:
    """Return the plain speech from a result."""
    return result.response.speech["plain"]["speech"]


async def test_completed_reply_and_conversation_id_reuse(
    hass: HomeAssistant,
    aioclient_mock,
    mock_agent_entry: MockConfigEntry,
    agent_url: str,
    agent_token: str,
) -> None:
    """A completed reply is spoken and the conversation ID is reused."""
    await _setup_entry(hass, mock_agent_entry)
    aioclient_mock.post(
        f"{agent_url}/conversation",
        json={"status": "completed", "reply": "The living room is 21 degrees."},
    )

    first = await _converse(hass, mock_agent_entry, "How warm is the living room?")
    assert first.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert _speech(first) == "The living room is 21 degrees."
    assert first.conversation_id

    first_method, first_url, first_data, first_headers = aioclient_mock.mock_calls[0]
    assert first_method == "POST"
    assert str(first_url) == f"{agent_url}/conversation"
    assert first_data == {
        "message": "How warm is the living room?",
        "conversationId": first.conversation_id,
    }
    assert first_headers["Authorization"] == f"Bearer {agent_token}"

    second = await _converse(
        hass, mock_agent_entry, "And the bedroom?", first.conversation_id
    )
    assert second.conversation_id == first.conversation_id
    assert aioclient_mock.mock_calls[1][2] == {
        "message": "And the bedroom?",
        "conversationId": first.conversation_id,
    }


async def test_failed_status_is_spoken_as_error(
    hass: HomeAssistant,
    aioclient_mock,
    mock_agent_entry: MockConfigEntry,
    agent_url: str,
) -> None:
    """A failed agent status becomes an error response with its code."""
    await _setup_entry(hass, mock_agent_entry)
    aioclient_mock.post(
        f"{agent_url}/conversation",
        json={
            "status": "failed",
            "error": {
                "code": "llm_timeout",
                "message": "The model did not respond in time.",
            },
        },
    )

    result = await _converse(hass, mock_agent_entry, "Turn on the light")

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert "llm_timeout" in _speech(result)
    assert "The model did not respond in time." in _speech(result)


async def test_failed_status_is_localized_in_portuguese(
    hass: HomeAssistant,
    aioclient_mock,
    mock_agent_entry: MockConfigEntry,
    agent_url: str,
) -> None:
    """Portuguese requests receive a Portuguese failure message."""
    await _setup_entry(hass, mock_agent_entry)
    aioclient_mock.post(
        f"{agent_url}/conversation",
        json={
            "status": "failed",
            "error": {"code": "tool_failed", "message": "Tool failed."},
        },
    )

    result = await _converse(
        hass, mock_agent_entry, "Liga a luz", language="pt-PT"
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert "não conseguiu" in _speech(result)
    assert "tool_failed" in _speech(result)


async def test_timeout_is_spoken_as_error(
    hass: HomeAssistant,
    aioclient_mock,
    mock_agent_entry: MockConfigEntry,
    agent_url: str,
) -> None:
    """A timeout returns a spoken error without crashing."""
    await _setup_entry(hass, mock_agent_entry)
    aioclient_mock.post(f"{agent_url}/conversation", exc=TimeoutError())

    result = await _converse(hass, mock_agent_entry, "Hello")

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert "too long" in _speech(result)


async def test_connection_error_is_spoken_as_error(
    hass: HomeAssistant,
    aioclient_mock,
    mock_agent_entry: MockConfigEntry,
    agent_url: str,
) -> None:
    """A connection failure returns a spoken error without crashing."""
    await _setup_entry(hass, mock_agent_entry)
    aioclient_mock.post(
        f"{agent_url}/conversation", exc=aiohttp.ClientConnectionError()
    )

    result = await _converse(hass, mock_agent_entry, "Hello")

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert "can't reach" in _speech(result)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "credentials"),
        (403, "credentials"),
        (500, "unavailable"),
        (418, "unexpected response"),
    ],
)
async def test_http_errors_are_spoken_as_errors(
    hass: HomeAssistant,
    aioclient_mock,
    mock_agent_entry: MockConfigEntry,
    agent_url: str,
    status: int,
    expected: str,
) -> None:
    """HTTP failures produce clear spoken errors."""
    await _setup_entry(hass, mock_agent_entry)
    aioclient_mock.post(f"{agent_url}/conversation", status=status)

    result = await _converse(hass, mock_agent_entry, "Hello")

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert expected in _speech(result)


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "completed", "reply": ""},
        {"status": "completed"},
        {"status": "made_up"},
        {"reply": "missing status"},
        [],
    ],
)
async def test_malformed_responses_are_spoken_as_errors(
    hass: HomeAssistant,
    aioclient_mock,
    mock_agent_entry: MockConfigEntry,
    agent_url: str,
    payload,
) -> None:
    """Malformed or unknown responses never become success."""
    await _setup_entry(hass, mock_agent_entry)
    aioclient_mock.post(f"{agent_url}/conversation", json=payload)

    result = await _converse(hass, mock_agent_entry, "Hello")

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert _speech(result)


async def test_empty_input_is_rejected_without_a_request(
    hass: HomeAssistant,
    aioclient_mock,
    mock_agent_entry: MockConfigEntry,
) -> None:
    """Whitespace-only input gets a clarification without contacting the agent."""
    await _setup_entry(hass, mock_agent_entry)

    result = await _converse(hass, mock_agent_entry, "   ")

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert _speech(result) == "Please say what you would like me to do."
    assert aioclient_mock.call_count == 0


async def test_entry_unload_unregisters_agent(
    hass: HomeAssistant,
    mock_agent_entry: MockConfigEntry,
) -> None:
    """Unloading the entry removes the conversation agent."""
    await _setup_entry(hass, mock_agent_entry)
    assert conversation.async_get_agent(hass, mock_agent_entry.entry_id) is not None

    assert await hass.config_entries.async_unload(mock_agent_entry.entry_id)
    await hass.async_block_till_done()

    assert conversation.async_get_agent(hass, mock_agent_entry.entry_id) is None
