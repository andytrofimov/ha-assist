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
- `app/llm_client.py` - DeepSeek/OpenAI-compatible fallback для запросов не про умный дом.
- `app/openai_compat.py` - вынесенная заготовка OpenAI-compatible логики, сейчас не зарегистрирована как эндпоинт.
- `custom_components/ha_assist/conversation.py` - Home Assistant conversation agent.
- `features/assistant_logic.feature` - BDD-сценарии успешных действий ассистента.
- `features/assistant_locations.feature` - BDD-сценарии комнат, этажей и комнаты колонки.
- `features/assistant_state_queries.feature` - BDD-сценарии вопросов состояния и сенсоров.
- `features/assistant_llm_fallback.feature` - BDD-сценарии LLM fallback для запросов не про умный дом.
- `features/assistant_negative.feature` - BDD-сценарии негативных и граничных случаев.
- `features/steps/assistant_logic_steps.py` - step definitions для `behave`.
- `tests/test_api_models.py` - pytest-тесты моделей `/assist`.
- `tests/test_conversation_memory.py` - pytest-тесты in-memory истории диалогов.
- `tests/test_llm_client.py` - pytest-тесты DeepSeek/OpenAI-compatible клиента без реального сетевого вызова.
- `tests/test_request_snapshot.py` - pytest-тест сохранения диагностического snapshot запроса.

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
- сохранение последнего полученного запроса в `last_assist_request.json` при запросе `/assist`.

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
- `last_assist_request.json` является локальным диагностическим файлом и должен оставаться в `.gitignore`.

## Проверки

Если зависимости доступны:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m behave
```

Быстрый запуск отдельных групп:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_api_models.py tests\test_conversation_memory.py tests\test_llm_client.py tests\test_request_snapshot.py
.\.venv\Scripts\python.exe -m behave features\assistant_logic.feature
.\.venv\Scripts\python.exe -m behave features\assistant_locations.feature
.\.venv\Scripts\python.exe -m behave features\assistant_state_queries.feature
.\.venv\Scripts\python.exe -m behave features\assistant_llm_fallback.feature
.\.venv\Scripts\python.exe -m behave features\assistant_negative.feature
```

`pytest` сейчас покрывает модели API, память диалога, LLM-клиент и сохранение `last_assist_request.json`.
Логику распознавания команд умного дома проверяют BDD-сценарии `behave` в `features/`.
Сценарии с известными будущими ожиданиями могут быть помечены тегом `@skip`, например числительные из голосового распознавания вместо цифр.
