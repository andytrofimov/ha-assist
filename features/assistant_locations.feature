# language: ru

#noinspection NonAsciiCharacters
Функция: Комнаты и этажи в логике ассистента
  Чтобы команды не срабатывали в неверной комнате
  Как пользователь Assist
  Я хочу, чтобы ассистент учитывал комнаты, этажи и колонку вызова

  Предыстория:
    Дано доступны сущности:
      | entity_id         | name                | state | aliases         | area_id | area_name | floor_id | floor_name |
      | light.living_room | Свет гостиная       | off   | свет в гостиной | living  | Гостиная  | floor_2  | Второй     |
      | light.kitchen     | Свет кухня          | off   | свет на кухне   | kitchen | Кухня     | floor_2  | Второй     |
      | switch.kettle     | Чайник              | off   |                 | kitchen | Кухня     | floor_2  | Второй     |
      | climate.office_ac | Кондиционер кабинет | off   | кондиционер     | office  | Кабинет   | floor_3  | Третий     |
      | light.office      | Свет кабинет        | off   |                 | office  | Кабинет   | floor_3  | Третий     |
      | scene.movie       | Режим кино          | off   |                 | living  | Гостиная  | floor_2  | Второй     |
    И доступны комнаты:
      | area_id | name     | floor_id | aliases |
      | living  | Гостиная | floor_2  |         |
      | kitchen | Кухня    | floor_2  |         |
      | office  | Кабинет  | floor_3  |         |
    И доступны этажи:
      | floor_id | name   | aliases     | level |
      | floor_2  | Второй | второй этаж | 2     |
      | floor_3  | Третий | третий этаж | 3     |

  Сценарий: Ошибка для неизвестной комнаты
    Когда пользователь говорит "выключи свет в гараже"
    Тогда ответ ассистента равен "Не нашла такую комнату."
    И ассистент не вызывает сервисы

  Сценарий: Ошибка когда комната не указана и найдено несколько комнат
    Когда пользователь говорит "выключи свет"
    Тогда ответ ассистента равен "Уточните комнату."
    И ассистент не вызывает сервисы

  Сценарий: Использовать комнату колонки если комната не указана
    Допустим запрос пришел из комнаты:
      | source_area_id | source_area_name |
      | kitchen        | Кухня            |
    Когда пользователь говорит "выключи свет"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id     |
      | light  | turn_off | light.kitchen |

  Сценарий: Выключить весь свет на этаже
    Когда пользователь говорит "выключи весь свет на втором этаже"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id         |
      | light  | turn_off | light.living_room |
      | light  | turn_off | light.kitchen     |

  Сценарий: Выключить все устройства на этаже
    Когда пользователь говорит "выключи все устройства на втором этаже"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id         |
      | light  | turn_off | light.living_room |
      | light  | turn_off | light.kitchen     |
      | switch | turn_off | switch.kettle     |
