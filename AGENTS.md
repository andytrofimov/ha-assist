# HA Assist Project Notes

Контекст для LLM

## Что это

Проект состоит из локального FastAPI-сервиса и кастомной интеграции Home Assistant.

FastAPI принимает запросы на `/assist`, получает текст пользователя и список exposed entities из Home Assistant, затем возвращает:

- `response`: короткий текст ответа пользователю;
- `service_calls`: список действий для Home Assistant.

Также есть `/health`.

Бэклог задач и багов для понимания направления развития проекта:

- Выключи свет везде или выключи везде свет - выключает домен во всех локациях
- "что случилось" - ассистент ошибочно отвечает не нашла такое устройство
- поддержка вспомогательных баттонов, свитчей и тд
- платформа кастомных команд в отдельном модуле: сколько времени, закажи продукты
- зачитывание туду списков, удаление элементов
- если в тексте есть намерение прекратить диалог (фразы отбой, не надо и тд) - ничего не делать и ничего не отвечать
- команда "это была ошибка" должна добавлять последний запрос в специальный туду список для дальнейшего разбора
- передача сообщения с одной колонки на другую (кастомный интент)

## Важные файлы

- `app/main.py` - FastAPI-приложение. В нем должны оставаться только `/assist` и `/health`.
- `app/api_models.py` - модели request/response для `/assist`.
- `ha_assist_core/__init__.py` - shim-пакет для импорта core из API-сервиса и тестов.
- `custom_components/ha_assist/ha_assist_core/assistant_logic.py` - основная логика разбора команд умного дома; на
  каждый запрос строит индекс нормализованных имен, alias, доменов и локаций entity.
- `custom_components/ha_assist/ha_assist_core/assistant_result.py` - модель результата core-логики, стандартные ответы
  и LLM fallback result.
- `custom_components/ha_assist/ha_assist_core/device_command.py` - команды устройств, сервисные вызовы, таймеры,
  bare-activation сцен/кнопок и добавление пунктов в todo.
- `custom_components/ha_assist/ha_assist_core/location_resolver.py` - комнаты, этажи, комната колонки и фильтрация
  entity по локации.
- `custom_components/ha_assist/ha_assist_core/state_query.py` - вопросы состояния, weather, форматирование процентов,
  температуры и русские склонения в ответах.
- `custom_components/ha_assist/ha_assist_core/text_matching.py` - общие helper-функции нормализации, вариантов слов и
  разбора aliases для matching-логики.
- `custom_components/ha_assist/ha_assist_core/assist_processor.py` - общий обработчик `/assist` payload для API-сервиса
  и локального режима интеграции.
- `custom_components/ha_assist/ha_assist_core/ha_parser.py` - модель `HaObject`.
- `custom_components/ha_assist/ha_assist_core/number_parser.py` - парсер цифр и русских числительных для процентов и
  длительностей.
- `custom_components/ha_assist/ha_assist_core/conversation_memory.py` - краткая in-memory история диалогов по
  `conversation_id`.
- `custom_components/ha_assist/ha_assist_core/custom_intents.py` - кастомные интенты, которые матчятся по
  нормализованному имени команды и выполняются раньше scene/button и обычной smart-home логики.
- `custom_components/ha_assist/ha_assist_core/llm_client.py` - DeepSeek/OpenAI-compatible fallback для запросов не про
  умный дом.
- `custom_components/ha_assist/conversation.py` - Home Assistant conversation agent.
- `custom_components/ha_assist/config_flow.py` - настройка интеграции, включая `local`, URL сервиса и API-ключ LLM для
  локального режима.
- `custom_components/ha_assist/manifest.json` - manifest интеграции и Python `requirements`.
- `features/assistant_logic.feature` - BDD-сценарии успешных действий ассистента.
- `features/assistant_custom_intents.feature` - BDD-сценарии кастомных интентов и их приоритета над smart-home логикой.
- `features/assistant_locations.feature` - BDD-сценарии комнат, этажей и комнаты колонки.
- `features/assistant_state_queries.feature` - BDD-сценарии вопросов состояния и сенсоров.
- `features/assistant_llm_fallback.feature` - BDD-сценарии LLM fallback для запросов не про умный дом.
- `features/assistant_negative.feature` - BDD-сценарии негативных и граничных случаев.
- `features/assistant_climate_temperature.feature` - BDD-сценарии установки температуры climate.
- `features/assistant_todo.feature` - BDD-сценарии добавления пунктов в todo-списки.
- `features/steps/assistant_logic_steps.py` - step definitions для `behave`.
- `tests/test_api_models.py` - pytest-тесты моделей `/assist`.
- `tests/test_conversation_memory.py` - pytest-тесты in-memory истории диалогов.
- `tests/test_llm_client.py` - pytest-тесты DeepSeek/OpenAI-compatible клиента без реального сетевого вызова.
- `tests/test_number_parser.py` - pytest-тесты парсинга цифр и русских числительных.
- `tests/test_request_snapshot.py` - pytest-тест сохранения диагностического snapshot запроса.
- `tests/test_assistant_logic_load.py` - локальный нагрузочный pytest-тест core-логики с разными запросами,
  повторами и фикстурой из объектов умного дома; выводит время выполнения в миллисекундах.

## Текущая логика

Core-логика поддерживает:

- включение entity по названию или alias только если это реально exposed entity в текущем доме;
- определение домена по именам и alias переданных `HaObject`, а также по ограниченному словарю общих пользовательских
  названий доменов вроде `свет -> light` и `кондиционер -> climate`; словарь применяется только к доменам, которые
  реально есть в текущем payload;
- выполнение custom intent до любых smart-home команд; сейчас поддержаны вопрос времени, короткая команда отмены и
  сохранение предыдущего запроса/ответа в todo для разбора ошибки;
- выполнение scene/button без явного командного глагола, если оригинальное или нормализованное обращение полностью
  совпадает с именем или alias; если таких scene/button несколько, ассистент просит уточнить комнату;
- шторы/ворота через `cover.open_cover` и `cover.close_cover`;
- matching по имени и aliases;
- фразы вида `кондиционер в спальне`, `температура в бассейне`;
- несколько комнат в одной фразе;
- команды на весь домен во всех локациях через "везде" или "весь/все" без явной комнаты, например свет,
  кондиционеры и вентиляторы;
- приоритет выбора: custom intent идет перед всем, затем bare-activation scene/button по полному совпадению имени или
  alias, затем конкретная сущность по имени или alias, и только потом broad-команды по домену вроде `выключи свет`;
- комнаты и этажи из справочников `areas`/`floors` и из привязки entity; alias entity не должен подменять комнату, если
  у entity уже задана настоящая комната;
- вопросы состояния;
- яркость света в процентах;
- отложенные и временные команды через `delay_seconds`;
- цифры и русские числительные в процентах яркости и длительностях;
- установку температуры climate через `climate.set_temperature`;
- поиск climate-отопления по явным `hvac_modes`/`state`, а не по названию entity;
- добавление пунктов в `todo` через `todo.add_item`; текст пункта после имени или alias списка считается свободным
  пользовательским текстом и может содержать слова устройств, комнат и командные глаголы без попытки выполнить их;
- успешное добавление в `todo` возвращает ответ с добавленным пунктом и названием выбранного списка;
- LLM fallback для запросов не про умный дом через `custom_components/ha_assist/ha_assist_core/llm_client.py`.
- передачу в LLM последних реплик беседы через `custom_components/ha_assist/ha_assist_core/conversation_memory.py`.
- получение из интеграции `area_id`, `area_name`, `floor_id`, `floor_name`, а также списков `areas` и `floors`.
- получение из интеграции `unit_of_measurement`, `device_class`, `hvac_modes`; например `%` используется для ответа
  процентных сенсоров без эвристик по названию entity.
- сохранение последнего полученного запроса в `last_assist_request.json` при запросе `/assist`.
- общие вопросы с упоминанием слов умного дома уходят в LLM fallback, если нет надежного совпадения с конкретной
  сущностью или понятной smart-home командой.
- слова комнат и этажей из имени entity не должны сами по себе выбирать домен или устройство; для локаций используются
  справочники комнат/этажей и привязка entity.
- результаты морфологической нормализации кешируются ограниченным LRU-кешем; `NormalizedText` неизменяемый, чтобы
  один результат можно было безопасно использовать в разных запросах.

## Home Assistant integration

`conversation.py` отправляет в `/assist` только entities, exposed для Assist:

```python
async_should_expose(self.hass, conversation.DOMAIN, state.entity_id)
```

Если в настройках интеграции включен `local`, `conversation.py` не обращается к HTTP-сервису, а вызывает
`custom_components/ha_assist/ha_assist_core/assist_processor.py` напрямую.
Если `local` выключен, интеграция отправляет тот же payload в настроенный `/assist` URL.
Сервисные вызовы без таймера выполняются через `intent.async_handle(...)`, чтобы контекст шел от диалога. Отложенные вызовы ждут `delay_seconds`, затем проходят тем же путем.

## Важные правила работы

- Все `Get-Content` вызывать с `-Encoding UTF8`.
- Не компилировать `conversation.py`, если в окружении нет пакета `homeassistant`.
- Не трогать файлы вне задачи.
- Актуализировать этот файл
- Комментарии писать на русском
- Комментарии писать через `#`, а не строковыми литералами.
- Многострочные строки писать через тройные кавычки.
- API-сервис читает API-ключ DeepSeek только из `deepseek_api_key.txt`; этот файл должен оставаться в `.gitignore`.
- Локальный режим интеграции может получать API-ключ LLM из настроек интеграции и передавать его в core без записи в
  файл.
- `last_assist_request.json` является локальным диагностическим файлом и должен оставаться в `.gitignore`.

## Проверки

Если зависимости доступны:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m behave
```

Быстрый запуск отдельных групп:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_api_models.py tests\test_conversation_memory.py tests\test_llm_client.py tests\test_number_parser.py tests\test_request_snapshot.py
.\.venv\Scripts\python.exe -m pytest -s tests\test_assistant_logic_load.py
.\.venv\Scripts\python.exe -m behave features\assistant_logic.feature
.\.venv\Scripts\python.exe -m behave features\assistant_custom_intents.feature
.\.venv\Scripts\python.exe -m behave features\assistant_locations.feature
.\.venv\Scripts\python.exe -m behave features\assistant_state_queries.feature
.\.venv\Scripts\python.exe -m behave features\assistant_llm_fallback.feature
.\.venv\Scripts\python.exe -m behave features\assistant_negative.feature
.\.venv\Scripts\python.exe -m behave features\assistant_climate_temperature.feature
.\.venv\Scripts\python.exe -m behave features\assistant_todo.feature
```

`pytest` сейчас покрывает модели API, контекст комнаты/этажа колонки, память диалога включая лимит истории и
conversation_id по умолчанию, LLM-клиент без реального сетевого вызова, парсер чисел и сохранение
`last_assist_request.json`.
Логику распознавания команд умного дома проверяют BDD-сценарии `behave` в `features/`.
BDD-примеры лучше держать как классы пользовательского поведения, а не как длинные списки близких фраз: похожие
формулировки переносить в параметризованные unit-тесты, если проверяется парсер или низкоуровневый helper.
Фикстуры BDD должны содержать конфликтующие entity разных доменов, scene/button, todo с пересекающимися alias и
несколько комнат/этажей, если сценарий проверяет matching, неоднозначность или защиту от случайных сервисных вызовов.
Сценарии с известными будущими ожиданиями могут быть помечены тегом `@skip`, например числительные из голосового распознавания вместо цифр.
Если надо запустить тесты - запускай все сразу, они быстро проходят
