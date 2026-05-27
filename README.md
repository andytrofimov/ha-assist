# Dysha's Assistant

Minimal Home Assistant Assist conversation agent that sends the user text and available entities to a local HTTP service.

## Local service

Run the FastAPI service from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## HACS installation

1. Add this repository to HACS as a custom repository.
2. Select the repository type `Integration`.
3. Install `Dysha's Assistant`.
4. Restart Home Assistant.
5. Add the integration from Settings -> Devices & services.

The default service URL is `http://127.0.0.1:8000/assist`.
