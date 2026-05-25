"""Conversation platform for HA Assist Service."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from aiohttp import ClientError, ClientResponseError

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_NAME, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ASSIST_URL, DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    async_add_entities([HaAssistConversationEntity(entry)])


class HaAssistConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
):
    """Conversation agent backed by a local HTTP service."""

    _attr_has_entity_name = True
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self._entry = entry
        self._attr_name = entry.data[CONF_NAME]
        self._attr_unique_id = entry.entry_id

    async def async_added_to_hass(self) -> None:
        """Register this entity as a conversation agent."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self._entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity as a conversation agent."""
        conversation.async_unset_agent(self.hass, self._entry)
        await super().async_will_remove_from_hass()

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return supported languages."""
        return MATCH_ALL

    async def async_process(
        self,
        user_input: conversation.ConversationInput,
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        response = intent.IntentResponse(language=user_input.language)

        try:
            result = await self._async_call_service(user_input)
            for service_call in result.get("service_calls", []):
                await self._async_execute_service_call(service_call, user_input)
            response.async_set_speech(str(result.get("response") or ""))
        except (TimeoutError, ClientError, ClientResponseError):
            _LOGGER.exception("Failed to call HA Assist service")
            response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                "HA Assist service is unavailable",
            )
        except Exception:
            _LOGGER.exception("Unexpected HA Assist service error")
            response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                "Unexpected HA Assist service error",
            )

        return conversation.ConversationResult(
            response=response,
            conversation_id=user_input.conversation_id,
        )

    async def _async_call_service(
        self,
        user_input: conversation.ConversationInput,
    ) -> dict[str, Any]:
        """Send the Assist request to the configured service."""
        session = async_get_clientsession(self.hass)
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            http_response = await session.post(
                self._entry.data[CONF_ASSIST_URL],
                json={
                    "text": user_input.text,
                    "language": user_input.language,
                    "conversation_id": user_input.conversation_id,
                    "entities": self._entities_payload(),
                },
            )
            http_response.raise_for_status()
            data = await http_response.json()

        if not isinstance(data, dict):
            raise ValueError("Assist service response must be a JSON object")
        return data

    def _entities_payload(self) -> list[dict[str, Any]]:
        """Return Home Assistant entities for the external service."""
        registry = er.async_get(self.hass)
        entities: list[dict[str, Any]] = []

        for state in self.hass.states.async_all():
            registry_entry = registry.async_get(state.entity_id)
            if registry_entry is not None and (
                registry_entry.disabled_by is not None
                or registry_entry.hidden_by is not None
            ):
                continue

            aliases = []
            if registry_entry is not None:
                aliases = intent.async_get_entity_aliases(
                    self.hass,
                    registry_entry,
                    state=state,
                )

            entities.append(
                {
                    "entity_id": state.entity_id,
                    "name": state.attributes.get(ATTR_FRIENDLY_NAME, state.entity_id),
                    "state": state.state,
                    "aliases": "/".join(aliases),
                }
            )

        return entities

    async def _async_execute_service_call(
        self,
        service_call: dict[str, Any],
        user_input: conversation.ConversationInput,
    ) -> None:
        """Execute a service call returned by the Assist service."""
        domain = service_call["domain"]
        service = service_call["service"]
        service_data = service_call.get("service_data") or {}

        await self.hass.services.async_call(
            domain,
            service,
            service_data,
            blocking=True,
            context=user_input.context,
        )
