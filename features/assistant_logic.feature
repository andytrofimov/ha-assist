# language: ru
#noinspection NonAsciiCharacters
Функция: Действия ассистента умного дома
  Чтобы управлять Home Assistant голосом
  Как пользователь Assist
  Я хочу, чтобы команды превращались в правильные сервисные вызовы

  Предыстория:
    Дано доступны сущности:
      | entity_id                 | name           | state  | aliases             | area_id   | area_name | floor_id | floor_name |
      | light.svet_gostinnaia     | Свет гостиная  | off    |                     | gostinaia | Гостиная  | vtoroi   | Второй     |
      | light.svet_kukhnia        | Свет кухня     | off    |                     | kukhnia   | Кухня     | vtoroi   | Второй     |
      | light.svet_kabinet        | Свет кабинет   | on     |                     | kabinet   | Кабинет   | tretii   | Третий     |
      | cover.0x54ef441000c8399e  | Штора спальня  | open   |                     | spalnia   | Спальня   | vtoroi   | Второй     |
      | cover.kontroller_vorot    | Ворота         | closed |                     | ulitsa    | Улица     | ulitsa   | Улица      |
      | scene.kino                | Сцена кино     | off    |                     | gostinaia | Гостиная  | vtoroi   | Второй     |
      | switch.krovat_massazh     | Массаж         | off    |                     | spalnia   | Спальня   | vtoroi   | Второй     |
      | switch.ventilation        | Device ABC     | off    | Включить вентиляцию | gostinaia | Гостиная  | vtoroi   | Второй     |
      | button.restart_zigbee     | Restart Zigbee | off    | Перезапустить зигби |           |           |          |            |
      | climate.air_conditioner_1 | Кондей спальня | off    | кондиционер         | spalnia   | Спальня   | vtoroi   | Второй     |
    И доступны комнаты:
      | area_id   | name     | floor_id | aliases |
      | gostinaia | Гостиная | vtoroi   |         |
      | kukhnia   | Кухня    | vtoroi   |         |
      | kabinet   | Кабинет  | tretii   |         |
      | spalnia   | Спальня  | vtoroi   |         |
    И доступны этажи:
      | floor_id | name   | aliases | level |
      | vtoroi   | Второй |         | 2     |
      | tretii   | Третий |         | 3     |

  Сценарий: Выполнить сцену по совпадению имени
    Когда пользователь говорит "сцена кино"
    Тогда ассистент вызывает сервисы:
      | domain | service | entity_id  |
      | scene  | turn_on | scene.kino |

  Сценарий: Выполнить сцену без явной команды если обращение совпадает с названием
    Когда пользователь говорит "Сцена кино"
    Тогда ассистент вызывает сервисы:
      | domain | service | entity_id  |
      | scene  | turn_on | scene.kino |

  Сценарий: Включить выключатель по совпадению имени с явной командой
    Когда пользователь говорит "включи массаж"
    Тогда ассистент вызывает сервисы:
      | domain | service | entity_id             |
      | switch | turn_on | switch.krovat_massazh |

  Сценарий: Нажать кнопку по алиасу
    Когда пользователь говорит "перезапусти зигби"
    Тогда ассистент вызывает сервисы:
      | domain | service | entity_id             |
      | button | press   | button.restart_zigbee |

  Структура сценария: Нажать кнопку без явной команды если обращение совпадает с названием или алиасом
    Когда пользователь говорит "<text>"
    Тогда ассистент вызывает сервисы:
      | domain | service | entity_id             |
      | button | press   | button.restart_zigbee |

    Примеры:
      | text                |
      | Restart Zigbee      |
      | Перезапустить зигби |

  Сценарий: Уточнить комнату если bare-обращение совпадает с несколькими сценами
    Дано доступны сущности:
      | entity_id       | name       | state | aliases | area_id   | area_name | floor_id | floor_name |
      | scene.kino_hall | Сцена кино | off   | кино    | gostinaia | Гостиная  | vtoroi   | Второй     |
      | scene.kino_bed  | Сцена кино | off   | кино    | spalnia   | Спальня   | vtoroi   | Второй     |
    И доступны комнаты:
      | area_id   | name     | floor_id | aliases |
      | gostinaia | Гостиная | vtoroi   |         |
      | spalnia   | Спальня  | vtoroi   |         |
    Когда пользователь говорит "сцена кино"
    Тогда ответ ассистента равен "Уточните комнату"
    И ассистент не вызывает сервисы

  Сценарий: Уточнить комнату если bare-обращение совпадает с несколькими кнопками
    Дано доступны сущности:
      | entity_id           | name           | state | aliases             | area_id   | area_name | floor_id | floor_name |
      | button.restart_hall | Restart Zigbee | off   | Перезапустить зигби | gostinaia | Гостиная  | vtoroi   | Второй     |
      | button.restart_bed  | Restart Zigbee | off   | Перезапустить зигби | spalnia   | Спальня   | vtoroi   | Второй     |
    И доступны комнаты:
      | area_id   | name     | floor_id | aliases |
      | gostinaia | Гостиная | vtoroi   |         |
      | spalnia   | Спальня  | vtoroi   |         |
    Когда пользователь говорит "Перезапустить зигби"
    Тогда ответ ассистента равен "Уточните комнату"
    И ассистент не вызывает сервисы

  Сценарий: Найти сущность по нормализованному алиасу
    Когда пользователь говорит "включи вентиляцию"
    Тогда ассистент вызывает сервисы:
      | domain | service | entity_id          |
      | switch | turn_on | switch.ventilation |

  Сценарий: Уникальный алиас не требует комнату в запросе
    Дано доступны сущности:
      | entity_id             | name          | state | aliases               | area_id   | area_name | floor_id | floor_name |
      | light.svet_gostinnaia | Свет гостиная | off   | праздничная подсветка | gostinaia | Гостиная  | vtoroi   | Второй     |
      | light.svet_kukhnia    | Свет кухня    | off   |                       | kukhnia   | Кухня     | vtoroi   | Второй     |
    Когда пользователь говорит "включи праздничную подсветку"
    Тогда ассистент вызывает сервисы:
      | domain | service | entity_id             |
      | light  | turn_on | light.svet_gostinnaia |

  Сценарий: Слово телевизор в названии сцены не должно требовать домен media_player
    Дано доступны сущности:
      | entity_id       | name            | state | aliases | area_id   | area_name | floor_id | floor_name |
      | scene.tv_mode   | Телевизор вечер | off   |         | gostinaia | Гостиная  | vtoroi   | Второй     |
      | media_player.tv | TV              | off   |         | spalnia   | Спальня   | vtoroi   | Второй     |
    Когда пользователь говорит "включи телевизор вечер"
    Тогда ассистент вызывает сервисы:
      | domain | service | entity_id     |
      | scene  | turn_on | scene.tv_mode |

  Сценарий: Объект с уникальным названием находится без указания комнаты
    Когда пользователь говорит "открой штору"
    Тогда ассистент вызывает сервисы:
      | domain | service    | entity_id                |
      | cover  | open_cover | cover.0x54ef441000c8399e |

  Сценарий: Закрыть cover-объект
    Когда пользователь говорит "закрой ворота"
    Тогда ассистент вызывает сервисы:
      | domain | service     | entity_id              |
      | cover  | close_cover | cover.kontroller_vorot |

  Сценарий: Включить климатическое устройство в указанной комнате
    Когда пользователь говорит "включи кондиционер в спальне"
    Тогда ассистент вызывает сервисы:
      | domain  | service | entity_id                 |
      | climate | turn_on | climate.air_conditioner_1 |

  Сценарий: Выключить свет в нескольких комнатах
    Когда пользователь говорит "выключи свет в гостиной и на кухне"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id             |
      | light  | turn_off | light.svet_gostinnaia |
      | light  | turn_off | light.svet_kukhnia    |

  Сценарий: Команда с яркостью, длительностью и шторой
    Когда пользователь говорит:
      """
      включи свет в гостиной на 15 процентов на 15 минут
      и закрой штору в спальне
      """
    Тогда ассистент вызывает сервисы:
      | domain | service     | entity_id                | brightness_pct | delay_seconds |
      | light  | turn_on     | light.svet_gostinnaia    | 15             |               |
      | light  | turn_off    | light.svet_gostinnaia    |                | 900           |
      | cover  | close_cover | cover.0x54ef441000c8399e |                |               |

  Сценарий: Включить климатическое устройство на длительность
    Когда пользователь говорит "включи кондиционер в спальне на полчаса"
    Тогда ассистент вызывает сервисы:
      | domain  | service  | entity_id                 | delay_seconds |
      | climate | turn_on  | climate.air_conditioner_1 |               |
      | climate | turn_off | climate.air_conditioner_1 | 1800          |

  Сценарий: Отложенно выключить свет
    Когда пользователь говорит "выключи свет в кабинете через 15 минут"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id          | delay_seconds |
      | light  | turn_off | light.svet_kabinet | 900           |

  Сценарий: Отложенно выключить свет с числительным из голосового ввода
    Когда пользователь говорит "выключи свет в кабинете через пятнадцать минут"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id          | delay_seconds |
      | light  | turn_off | light.svet_kabinet | 900           |

  Сценарий: Включить свет на два часа
    Когда пользователь говорит "включи свет в гостиной на два часа"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id             | delay_seconds |
      | light  | turn_on  | light.svet_gostinnaia |               |
      | light  | turn_off | light.svet_gostinnaia | 7200          |

  Структура сценария: Граничные значения яркости ограничиваются диапазоном Home Assistant
    Когда пользователь говорит "<text>"
    Тогда ассистент вызывает сервисы:
      | domain | service | entity_id             | brightness_pct |
      | light  | turn_on | light.svet_gostinnaia | <brightness>   |

    Примеры:
      | text                                           | brightness |
      | включи свет в гостиной на 0 процентов          | 1          |
      | включи свет в гостиной на 1 процент            | 1          |
      | включи свет в гостиной на 100 процентов        | 100        |
      | включи свет в гостиной на 101 процент          | 100        |
      | включи свет в гостиной на ноль процентов       | 1          |
      | включи свет в гостиной на один процент         | 1          |
      | включи свет в гостиной на пятнадцать процентов | 15         |
      | включи свет в гостиной на сто процентов        | 100        |
      | включи свет в гостиной на сто один процент     | 100        |
