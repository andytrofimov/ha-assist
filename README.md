# HA Assist Service

Minimal Home Assistant Assist conversation agent that sends the user text and available entities to a local HTTP service.

## HACS installation

1. Add this repository to HACS as a custom repository.
2. Select the repository type `Integration`.
3. Install `HA Assist Service`.
4. Restart Home Assistant.
5. Add the integration from Settings -> Devices & services.

The default service URL is `http://127.0.0.1:8000/assist`.
