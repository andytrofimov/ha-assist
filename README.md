# Dysha's Assistant

Minimal Home Assistant Assist conversation agent that sends the user text and available entities to a local HTTP service.

## Local service

Run the FastAPI service from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Optional DeepSeek fallback for non-smart-home requests.
Put the API key into `deepseek_api_key.txt` in the repository root:

```powershell
Set-Content -Encoding UTF8 deepseek_api_key.txt "..."
```

The fallback sends the recent conversation history for the same `conversation_id`,
so follow-up questions keep context while the service process is running.

Each `/assist` request also saves the latest exposed entities payload to
`last_entities.json` in the repository root for local debugging.

## HACS installation

1. Add this repository to HACS as a custom repository.
2. Select the repository type `Integration`.
3. Install `Dysha's Assistant`.
4. Restart Home Assistant.
5. Add the integration from Settings -> Devices & services.

The default service URL is `http://127.0.0.1:8000/assist`.
