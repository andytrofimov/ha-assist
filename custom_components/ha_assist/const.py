"""Constants for Dysha's Assistant."""

from homeassistant.const import Platform

DOMAIN = "ha_assist"
PLATFORMS = [Platform.CONVERSATION]

CONF_ASSIST_URL = "assist_url"
CONF_LOCAL = "local"
CONF_LLM_API_KEY = "llm_api_key"
DEFAULT_ASSIST_URL = "http://127.0.0.1:8000/assist"
DEFAULT_TIMEOUT = 30
