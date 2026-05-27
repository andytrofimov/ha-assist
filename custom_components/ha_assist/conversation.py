"""Платформа диалогового агента HA Assist Service."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from aiohttp import ClientError, ClientResponseError

from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_NAME, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    intent,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ASSIST_URL, DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Создает сущность диалогового агента для записи интеграции."""
    async_add_entities([HaAssistConversationEntity(entry)])


class HaAssistConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
):
    """Диалоговый агент, который обращается к локальному HTTP-сервису."""

    _attr_has_entity_name = True
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(self, entry: ConfigEntry) -> None:
        """Запоминает config entry и настраивает имя сущности агента."""
        self._entry = entry
        self._attr_name = entry.data[CONF_NAME]
        self._attr_unique_id = entry.entry_id

    async def async_added_to_hass(self) -> None:
        """Регистрирует эту сущность как агента диалогов Home Assistant."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self._entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """Снимает регистрацию агента диалогов при выгрузке сущности."""
        conversation.async_unset_agent(self.hass, self._entry)
        await super().async_will_remove_from_hass()

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Возвращает список поддерживаемых языков."""
        return MATCH_ALL

    async def async_process(
        self,
        user_input: conversation.ConversationInput,
    ) -> conversation.ConversationResult:
        """Обрабатывает фразу пользователя и возвращает ответ диалога."""
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
        """Отправляет запрос пользователя в настроенный локальный сервис."""
        session = async_get_clientsession(self.hass)
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            http_response = await session.post(
                self._entry.data[CONF_ASSIST_URL],
                json={
                    "text": user_input.text,
                    "language": user_input.language,
                    "conversation_id": user_input.conversation_id,
                    "entities": self._entities_payload(),
                    "areas": self._areas_payload(),
                    "floors": self._floors_payload(),
                    **self._source_payload(user_input),
                },
            )
            http_response.raise_for_status()
            data = await http_response.json()

        if not isinstance(data, dict):
            raise ValueError("Assist service response must be a JSON object")
        return data

    def _entities_payload(self) -> list[dict[str, Any]]:
        """Собирает exposed-сущности Home Assistant для локального сервиса."""
        registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)
        area_registry = ar.async_get(self.hass)
        floor_registry = fr.async_get(self.hass)
        entities: list[dict[str, Any]] = []

        for state in self.hass.states.async_all():
            registry_entry = registry.async_get(state.entity_id)
            if registry_entry is not None and (
                registry_entry.disabled_by is not None
                or registry_entry.hidden_by is not None
            ):
                continue
            if not async_should_expose(
                self.hass,
                conversation.DOMAIN,
                state.entity_id,
            ):
                continue

            aliases = []
            if registry_entry is not None:
                aliases = intent.async_get_entity_aliases(
                    self.hass,
                    registry_entry,
                    state=state,
                )

            area_id = self._entity_area_id(registry_entry, device_registry)
            area = area_registry.async_get_area(area_id) if area_id else None
            floor_id = self._area_floor_id(area)
            floor = floor_registry.async_get_floor(floor_id) if floor_id else None

            entities.append(
                {
                    "entity_id": state.entity_id,
                    "name": state.attributes.get(ATTR_FRIENDLY_NAME, state.entity_id),
                    "state": state.state,
                    "aliases": "/".join(aliases),
                    "area_id": area_id,
                    "area_name": self._entry_name(area),
                    "floor_id": floor_id,
                    "floor_name": self._entry_name(floor),
                }
            )

        return entities

    def _areas_payload(self) -> list[dict[str, Any]]:
        """Собирает справочник пространств Home Assistant."""
        area_registry = ar.async_get(self.hass)
        return [
            {
                "area_id": self._entry_id(area),
                "name": self._entry_name(area),
                "floor_id": self._area_floor_id(area),
                "aliases": self._entry_aliases(area),
            }
            for area in area_registry.async_list_areas()
        ]

    def _floors_payload(self) -> list[dict[str, Any]]:
        """Собирает справочник этажей Home Assistant."""
        floor_registry = fr.async_get(self.hass)
        return [
            {
                "floor_id": self._entry_id(floor),
                "name": self._entry_name(floor),
                "aliases": self._entry_aliases(floor),
                "level": getattr(floor, "level", None),
            }
            for floor in floor_registry.async_list_floors()
        ]

    def _source_payload(
        self,
        user_input: conversation.ConversationInput,
    ) -> dict[str, Any]:
        """Определяет комнату устройства, с которого пришел голосовой запрос."""
        device_id = getattr(user_input, "device_id", None)
        if device_id is None:
            return {}

        device_registry = dr.async_get(self.hass)
        area_registry = ar.async_get(self.hass)
        floor_registry = fr.async_get(self.hass)
        device = device_registry.async_get(device_id)
        area_id = getattr(device, "area_id", None) if device is not None else None
        area = area_registry.async_get_area(area_id) if area_id else None
        floor_id = self._area_floor_id(area)
        floor = floor_registry.async_get_floor(floor_id) if floor_id else None

        return {
            "source_device_id": device_id,
            "source_area_id": area_id,
            "source_area_name": self._entry_name(area),
            "source_floor_id": floor_id,
            "source_floor_name": self._entry_name(floor),
        }

    def _entity_area_id(
        self,
        registry_entry: er.RegistryEntry | None,
        device_registry: dr.DeviceRegistry,
    ) -> str | None:
        """Возвращает пространство entity с учетом привязанного устройства."""
        if registry_entry is None:
            return None

        area_id = getattr(registry_entry, "area_id", None)
        if area_id:
            return area_id

        device_id = getattr(registry_entry, "device_id", None)
        if device_id is None:
            return None

        device = device_registry.async_get(device_id)
        return getattr(device, "area_id", None) if device is not None else None

    def _entry_id(self, entry: Any) -> str | None:
        """Возвращает id записи registry независимо от версии Home Assistant."""
        return getattr(entry, "id", None) or getattr(entry, "area_id", None) or getattr(
            entry,
            "floor_id",
            None,
        )

    def _entry_name(self, entry: Any) -> str | None:
        """Возвращает имя записи registry."""
        return getattr(entry, "name", None) if entry is not None else None

    def _entry_aliases(self, entry: Any) -> str:
        """Возвращает псевдонимы записи registry одной строкой."""
        aliases = getattr(entry, "aliases", None) if entry is not None else None
        if not aliases:
            return ""
        return "/".join(str(alias) for alias in aliases)

    def _area_floor_id(self, area: Any) -> str | None:
        """Возвращает этаж пространства, если он задан."""
        return getattr(area, "floor_id", None) if area is not None else None

    async def _async_execute_service_call(
        self,
        service_call: dict[str, Any],
        user_input: conversation.ConversationInput,
    ) -> None:
        """Выполняет сервисный вызов из ответа локального сервиса."""
        delay_seconds = service_call.get("delay_seconds")
        if isinstance(delay_seconds, int | float) and delay_seconds > 0:
            self.hass.async_create_task(
                self._async_delayed_execute_service_call(service_call, user_input),
            )
            return

        await self._async_execute_assist_intent(service_call, user_input)

    async def _async_execute_assist_intent(
        self,
        service_call: dict[str, Any],
        user_input: conversation.ConversationInput,
    ) -> None:
        """Выполняет обычный сервисный вызов через Assist intent API."""
        intent_type, slots = self._assist_intent_payload(service_call)
        await intent.async_handle(
            self.hass,
            conversation.DOMAIN,
            intent_type,
            slots=slots,
            text_input=user_input.text,
            context=user_input.context,
            language=user_input.language,
            assistant=conversation.DOMAIN,
            conversation_agent_id=self.entity_id,
        )

    def _assist_intent_payload(
        self,
        service_call: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        """Преобразует сервисный вызов в intent и slots для Assist."""
        domain = service_call["domain"]
        service = service_call["service"]
        service_data = service_call.get("service_data") or {}
        entity_id = service_data["entity_id"]

        slots: dict[str, Any] = {
            "name": {
                "value": entity_id,
                "text": entity_id,
            },
            "domain": {
                "value": [domain],
            },
        }
        if brightness_pct := service_data.get("brightness_pct"):
            slots["brightness"] = {
                "value": brightness_pct,
            }

        if service == "turn_on":
            return intent.INTENT_TURN_ON, slots
        if service == "turn_off":
            return intent.INTENT_TURN_OFF, slots
        if domain == "cover" and service in {"open_cover", "close_cover"}:
            slots["position"] = {
                "value": 100 if service == "open_cover" else 0,
            }
            return intent.INTENT_SET_POSITION, slots

        raise ValueError(f"Unsupported Assist service call: {service_call}")

    async def _async_delayed_execute_service_call(
        self,
        service_call: dict[str, Any],
        user_input: conversation.ConversationInput,
    ) -> None:
        """Выполняет сервисный вызов после указанной задержки."""
        await asyncio.sleep(float(service_call["delay_seconds"]))
        delayed_call = {
            key: value for key, value in service_call.items() if key != "delay_seconds"
        }
        await self._async_execute_service_call(delayed_call, user_input)
