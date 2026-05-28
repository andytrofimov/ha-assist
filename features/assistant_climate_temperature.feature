# language: ru
#noinspection NonAsciiCharacters
Функция: Установка температуры климатических устройств
  Чтобы управлять кондиционерами и термостатами голосом
  Как пользователь Assist
  Я хочу задавать целевую температуру числом или числительным

  Предыстория:
    Дано доступны сущности:
      | entity_id                 | name              | state | aliases     | area_id | area_name | floor_id | floor_name | hvac_modes    | device_class |
      | climate.air_conditioner_1 | Кондей спальня    | off   | кондиционер | spalnia | Спальня   | vtoroi   | Второй     | cool/heat/off |              |
      | climate.thermostat_1      | Термостат кабинет | heat  | термостат   | kabinet | Кабинет   | tretii   | Третий     | heat/off      | thermostat   |
    И доступны комнаты:
      | area_id | name    | floor_id | aliases |
      | spalnia | Спальня | vtoroi   |         |
      | kabinet | Кабинет | tretii   |         |
    И доступны этажи:
      | floor_id | name   | aliases | level |
      | vtoroi   | Второй |         | 2     |
      | tretii   | Третий |         | 3     |

  Сценарий: Установить температуру климатического устройства цифрой
    Когда пользователь говорит "поставь кондиционер в спальне на 22 градуса"
    Тогда ассистент вызывает сервисы:
      | domain  | service         | entity_id                 | temperature |
      | climate | set_temperature | climate.air_conditioner_1 | 22          |

  Сценарий: Установить температуру климатического устройства числительным
    Когда пользователь говорит "поставь кондиционер в спальне на двадцать два градуса"
    Тогда ассистент вызывает сервисы:
      | domain  | service         | entity_id                 | temperature |
      | climate | set_temperature | climate.air_conditioner_1 | 22          |

  Сценарий: Установить температуру отопительного устройства числительным
    Когда пользователь говорит "установи отопление в кабинете на двадцать один градус"
    Тогда ассистент вызывает сервисы:
      | domain  | service         | entity_id            | temperature |
      | climate | set_temperature | climate.thermostat_1 | 21          |

  Сценарий: Установка температуры без устройства и комнаты требует уточнения
    Когда пользователь говорит "поставь температуру на 22 градуса"
    Тогда ответ ассистента равен "Не нашла такое устройство"
    И ассистент не вызывает сервисы

  Сценарий: Температуру нельзя установить неклиматическому устройству
    Дано доступны сущности:
      | entity_id             | name          | state | aliases | area_id   | area_name | floor_id | floor_name |
      | light.svet_gostinnaia | Свет гостиная | off   |         | gostinaia | Гостиная  | vtoroi   | Второй     |
    Когда пользователь говорит "поставь свет в гостиной на 22 градуса"
    Тогда ассистент просит LLM fallback
    И ответ ассистента пустой
    И ассистент не вызывает сервисы
