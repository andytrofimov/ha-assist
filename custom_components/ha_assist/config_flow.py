"""Config flow for Dysha's Assistant."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .const import (
    CONF_ASSIST_URL,
    CONF_LLM_API_KEY,
    CONF_LLM_API_URL,
    CONF_LOCAL,
    DEFAULT_ASSIST_URL,
    DEFAULT_LLM_API_URL,
    DOMAIN,
)


class HaAssistConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dysha's Assistant."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Создает форму настроек для существующей записи интеграции."""
        return HaAssistOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            assist_url = user_input[CONF_ASSIST_URL].strip()
            llm_api_url = user_input[CONF_LLM_API_URL].strip()
            try:
                assist_url = cv.url(assist_url)
                llm_api_url = cv.url(llm_api_url)
            except vol.Invalid:
                errors["base"] = "invalid_url"
            else:
                await self.async_set_unique_id(assist_url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_ASSIST_URL: assist_url,
                        CONF_LOCAL: user_input[CONF_LOCAL],
                        CONF_LLM_API_KEY: user_input.get(CONF_LLM_API_KEY, "").strip(),
                        CONF_LLM_API_URL: llm_api_url,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                assist_schema(
                    name="Dysha's Assistant",
                    local=True,
                    assist_url=DEFAULT_ASSIST_URL,
                    llm_api_url=DEFAULT_LLM_API_URL,
                ),
                user_input,
            ),
            errors=errors,
        )


class HaAssistOptionsFlow(OptionsFlow):
    """Handle options flow for Dysha's Assistant."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Запоминает существующую запись интеграции."""
        self._entry = entry

    async def async_step_init(
            self,
            user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle options form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            assist_url = user_input[CONF_ASSIST_URL].strip()
            llm_api_url = user_input[CONF_LLM_API_URL].strip()
            try:
                assist_url = cv.url(assist_url)
                llm_api_url = cv.url(llm_api_url)
            except vol.Invalid:
                errors["base"] = "invalid_url"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_LOCAL: user_input[CONF_LOCAL],
                        CONF_ASSIST_URL: assist_url,
                        CONF_LLM_API_KEY: user_input.get(CONF_LLM_API_KEY, "").strip(),
                        CONF_LLM_API_URL: llm_api_url,
                    },
                )

        return self.async_show_form(
            step_id="init",
            data_schema=assist_schema(
                name=self._entry.options.get(CONF_NAME, self._entry.data[CONF_NAME]),
                local=self._entry.options.get(
                    CONF_LOCAL,
                    self._entry.data.get(CONF_LOCAL, False),
                ),
                assist_url=self._entry.options.get(
                    CONF_ASSIST_URL,
                    self._entry.data.get(CONF_ASSIST_URL, DEFAULT_ASSIST_URL),
                ),
                llm_api_key=self._entry.options.get(
                    CONF_LLM_API_KEY,
                    self._entry.data.get(CONF_LLM_API_KEY, ""),
                ),
                llm_api_url=self._entry.options.get(
                    CONF_LLM_API_URL,
                    self._entry.data.get(CONF_LLM_API_URL, DEFAULT_LLM_API_URL),
                ),
            ),
            errors=errors,
        )


def assist_schema(
        name: str,
        local: bool,
        assist_url: str,
        llm_api_key: str = "",
        llm_api_url: str = DEFAULT_LLM_API_URL,
) -> vol.Schema:
    """Возвращает общую схему первичной настройки и options flow."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=name): str,
            vol.Required(CONF_LOCAL, default=local): bool,
            vol.Required(CONF_ASSIST_URL, default=assist_url): TextSelector(
                TextSelectorConfig(type=TextSelectorType.URL)
            ),
            vol.Optional(CONF_LLM_API_KEY, default=llm_api_key): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_LLM_API_URL, default=llm_api_url): TextSelector(
                TextSelectorConfig(type=TextSelectorType.URL)
            ),
        }
    )
