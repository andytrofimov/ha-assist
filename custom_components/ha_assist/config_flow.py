"""Config flow for HA Assist Service."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .const import CONF_ASSIST_URL, DEFAULT_ASSIST_URL, DOMAIN


class HaAssistConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Assist Service."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            assist_url = user_input[CONF_ASSIST_URL].strip()
            try:
                assist_url = cv.url(assist_url)
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
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_NAME, default="HA Assist Service"): str,
                        vol.Required(CONF_ASSIST_URL, default=DEFAULT_ASSIST_URL): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.URL)
                        ),
                    }
                ),
                user_input,
            ),
            errors=errors,
        )
