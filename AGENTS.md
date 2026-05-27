# HA Assist Project Notes

Контекст для LLM

## Что это

Проект состоит из локального FastAPI-сервиса и кастомной интеграции Home Assistant.

FastAPI принимает запросы на `/assist`, получает текст пользователя и список exposed entities из Home Assistant, затем возвращает:

- `response`: короткий текст ответа пользователю;
- `service_calls`: список действий для Home Assistant.

Также есть `/health`.

## Важные файлы

- `app/main.py` - FastAPI-приложение. В нем должны оставаться только `/assist` и `/health`.
- `app/assistant_logic.py` - основная логика разбора команд умного дома.
- `app/api_models.py` - модели request/response для `/assist`.
- `app/ha_parser.py` - модель `HaObject`.
- `app/conversation_memory.py` - краткая in-memory история диалогов по `conversation_id`.
- `app/entity_snapshot.py` - сохранение последнего списка exposed entities в `last_entities.json`.
- `app/llm_client.py` - DeepSeek/OpenAI-compatible fallback для запросов не про умный дом.
- `app/openai_compat.py` - вынесенная заготовка OpenAI-compatible логики, сейчас не зарегистрирована как эндпоинт.
- `custom_components/ha_assist/conversation.py` - Home Assistant conversation agent.
- `tests/test_assistant_logic.py` - pytest-тесты логики ассистента.

## Текущая логика

`app/assistant_logic.py` поддерживает:

- включение включаемых entity по названию: сцены, switch, light, climate и т.д.;
- шторы/ворота через `cover.open_cover` и `cover.close_cover`;
- matching по имени и aliases;
- фразы вида `кондиционер в спальне`, `температура в бассейне`;
- несколько комнат в одной фразе;
- этажи, если entity/alias содержит этаж;
- вопросы состояния;
- яркость света в процентах;
- отложенные и временные команды через `delay_seconds`;
- LLM fallback для запросов не про умный дом через `app/llm_client.py`.
- передачу в LLM последних реплик беседы через `app/conversation_memory.py`.
- получение из интеграции `area_id`, `area_name`, `floor_id`, `floor_name`, а также списков `areas` и `floors`.
- сохранение последнего полученного списка entities в `last_entities.json` при запросе `/assist`.

## Home Assistant integration

`conversation.py` отправляет в `/assist` только entities, exposed для Assist:

```python
async_should_expose(self.hass, conversation.DOMAIN, state.entity_id)
```

Сервисные вызовы без таймера выполняются через `intent.async_handle(...)`, чтобы контекст шел от диалога. Отложенные вызовы ждут `delay_seconds`, затем проходят тем же путем.

## Важные правила работы

- Все `Get-Content` вызывать с `-Encoding UTF8`.
- Не компилировать `conversation.py`, если в окружении нет пакета `homeassistant`.
- Не трогать файлы вне задачи.
- Комментарии писать на русском
- Комментарии писать через `#`, а не строковыми литералами.
- Многострочные строки писать через тройные кавычки.
- API-ключ DeepSeek читать только из `deepseek_api_key.txt`; этот файл должен оставаться в `.gitignore`.
- `last_entities.json` является локальным диагностическим файлом и должен оставаться в `.gitignore`.

## Проверки

Если зависимости доступны:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_assistant_logic.py
```
