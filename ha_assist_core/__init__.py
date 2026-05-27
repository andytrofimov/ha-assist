from pathlib import Path

# API-сервис и тесты импортируют этот пакет из корня репозитория.
# Реальная логика лежит внутри интеграции, чтобы HACS/HA получали ее вместе с custom component.
_INTEGRATION_CORE = (
        Path(__file__).resolve().parent.parent
        / "custom_components"
        / "ha_assist"
        / "ha_assist_core"
)

if _INTEGRATION_CORE.is_dir():
    __path__.append(str(_INTEGRATION_CORE))
