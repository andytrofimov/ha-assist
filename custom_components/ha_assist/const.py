"""Constants for HA Assist Service."""

from homeassistant.const import Platform

DOMAIN = "ha_assist"
PLATFORMS = [Platform.CONVERSATION]

CONF_ASSIST_URL = "assist_url"
DEFAULT_ASSIST_URL = "http://127.0.0.1:8000/assist"
DEFAULT_TIMEOUT = 30
