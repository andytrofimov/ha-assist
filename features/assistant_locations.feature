# language: ru

#noinspection NonAsciiCharacters
Функция: Комнаты и этажи в логике ассистента
  Чтобы команды не срабатывали в неверной комнате
  Как пользователь Assist
  Я хочу, чтобы ассистент учитывал комнаты, этажи и колонку вызова

  Предыстория:
    Дано доступны сущности:
      | entity_id                              | name            | state | aliases | area_id   | area_name | floor_id | floor_name |
      | light.svet_gostinnaia                  | Свет гостиная   | off   |         | gostinaia | Гостиная  | vtoroi   | Второй     |
      | light.svet_kukhnia                     | Свет кухня      | off   |         | kukhnia   | Кухня     | vtoroi   | Второй     |
      | switch.chainik                         | Чайник          | off   |         | kukhnia   | Кухня     | vtoroi   | Второй     |
      | light.svet_kabinet                     | Свет кабинет    | on    |         | kabinet   | Кабинет   | tretii   | Третий     |
      | scene.kino                             | Сцена кино      | off   |         | gostinaia | Гостиная  | vtoroi   | Второй     |
      | light.yeelink_ceil43_9a4b_light        | Люстра гостиная | off   |         | gostinaia | Гостиная  | vtoroi   | Второй     |
      | light.yeelink_ceilc_a6e6_ambient_light | Подсветка кухня | off   |         | kukhnia   | Кухня     | vtoroi   | Второй     |
    И доступны комнаты:
      | area_id   | name     | floor_id | aliases |
      | gostinaia | Гостиная | vtoroi   | зал     |
      | kukhnia   | Кухня    | vtoroi   |         |
      | kabinet   | Кабинет  | tretii   |         |
    И доступны этажи:
      | floor_id | name   | aliases | level |
      | vtoroi   | Второй | жилой   | 2     |
      | tretii   | Третий |         | 3     |

  Сценарий: Использовать комнату колонки если комната не указана
    Допустим запрос пришел из комнаты:
      | source_area_id | source_area_name |
      | kukhnia        | Кухня            |
    Когда пользователь говорит "выключи свет"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id          |
      | light  | turn_off | light.svet_kukhnia |

  Сценарий: Команда света не должна запускать сцену с пересекающимся алиасом
    Дано доступны сущности:
      | entity_id              | name           | state | aliases | area_id | area_name | floor_id | floor_name |
      | light.svet_kabinet     | Свет кабинет   | off   |         | kabinet | Кабинет   | tretii   | Третий     |
      | scene.vechernii_rezhim | Вечерний режим | off   | свет    | kabinet | Кабинет   | tretii   | Третий     |
    И доступны комнаты:
      | area_id | name    | floor_id | aliases |
      | kabinet | Кабинет | tretii   |         |
    Допустим запрос пришел из комнаты:
      | source_area_id | source_area_name |
      | kabinet        | Кабинет          |
    Когда пользователь говорит "включи свет"
    Тогда ассистент вызывает сервисы:
      | domain | service | entity_id          |
      | light  | turn_on | light.svet_kabinet |

  Структура сценария: Параметр яркости не должен считаться неизвестной комнатой
    Допустим запрос пришел из комнаты:
      | source_area_name |
      | Кабинет          |
    Когда пользователь говорит "<text>"
    Тогда ассистент вызывает сервисы:
      | domain | service | entity_id          | brightness_pct |
      | light  | turn_on | light.svet_kabinet | <brightness>   |

    Примеры:
      | text                               | brightness |
      | включи свет на пятьдесят процентов | 50         |
      | включи свет на 50 процентов        | 50         |

  Сценарий: Явная комната важнее комнаты колонки
    Допустим запрос пришел из комнаты:
      | source_area_id | source_area_name |
      | kukhnia        | Кухня            |
    Когда пользователь говорит "выключи свет в гостиной"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id                       |
      | light  | turn_off | light.svet_gostinnaia           |
      | light  | turn_off | light.yeelink_ceil43_9a4b_light |

  Сценарий: Найти комнату по алиасу
    Когда пользователь говорит "выключи свет в зале"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id                       |
      | light  | turn_off | light.svet_gostinnaia           |
      | light  | turn_off | light.yeelink_ceil43_9a4b_light |

  Сценарий: Выключить весь свет на этаже
    Когда пользователь говорит "выключи свет на втором этаже"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id                              |
      | light  | turn_off | light.svet_gostinnaia                  |
      | light  | turn_off | light.svet_kukhnia                     |
      | light  | turn_off | light.yeelink_ceil43_9a4b_light        |
      | light  | turn_off | light.yeelink_ceilc_a6e6_ambient_light |

  Структура сценария: Включить или выключить весь домен во всех локациях
    Дано доступны сущности:
      | entity_id                    | name                | state | aliases     | area_id   | area_name | floor_id | floor_name |
      | light.svet_gostinnaia        | Свет гостиная       | on    |             | gostinaia | Гостиная  | vtoroi   | Второй     |
      | light.svet_kukhnia           | Свет кухня          | on    |             | kukhnia   | Кухня     | vtoroi   | Второй     |
      | switch.chainik               | Чайник              | on    |             | kukhnia   | Кухня     | vtoroi   | Второй     |
      | climate.konditsioner_spalnia | Кондиционер спальня | cool  | кондиционер | spalnia   | Спальня   | vtoroi   | Второй     |
      | climate.konditsioner_kabinet | Кондиционер кабинет | cool  | кондиционер | kabinet   | Кабинет   | tretii   | Третий     |
      | fan.ventiliator_gostinnaia   | Вентилятор гостиная | on    | вентилятор  | gostinaia | Гостиная  | vtoroi   | Второй     |
      | fan.ventiliator_spalnia      | Вентилятор спальня  | on    | вентилятор  | spalnia   | Спальня   | vtoroi   | Второй     |
    И доступны комнаты:
      | area_id   | name     | floor_id | aliases |
      | gostinaia | Гостиная | vtoroi   |         |
      | kukhnia   | Кухня    | vtoroi   |         |
      | spalnia   | Спальня  | vtoroi   |         |
      | kabinet   | Кабинет  | tretii   |         |
    Когда пользователь говорит "<text>"
    Тогда ассистент вызывает сервисы:
      | domain   | service   | entity_id  |
      | <domain> | <service> | <entity_1> |
      | <domain> | <service> | <entity_2> |

    Примеры:
      | text                      | service  | domain  | entity_1                     | entity_2                     |
      | выключи свет везде        | turn_off | light   | light.svet_gostinnaia        | light.svet_kukhnia           |
      | выключи везде свет        | turn_off | light   | light.svet_gostinnaia        | light.svet_kukhnia           |
      | включи весь свет          | turn_on  | light   | light.svet_gostinnaia        | light.svet_kukhnia           |
      | выключи все кондиционеры  | turn_off | climate | climate.konditsioner_spalnia | climate.konditsioner_kabinet |
      | включи кондиционеры везде | turn_on  | climate | climate.konditsioner_spalnia | climate.konditsioner_kabinet |
      | включи все вентиляторы    | turn_on  | fan     | fan.ventiliator_gostinnaia   | fan.ventiliator_spalnia      |

  Сценарий: Найти этаж по алиасу
    Когда пользователь говорит "выключи свет на жилом этаже"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id                              |
      | light  | turn_off | light.svet_gostinnaia                  |
      | light  | turn_off | light.svet_kukhnia                     |
      | light  | turn_off | light.yeelink_ceil43_9a4b_light        |
      | light  | turn_off | light.yeelink_ceilc_a6e6_ambient_light |

  Сценарий: Выключить все устройства на этаже
    Когда пользователь говорит "выключи все на втором этаже"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id                              |
      | light  | turn_off | light.svet_gostinnaia                  |
      | light  | turn_off | light.svet_kukhnia                     |
      | switch | turn_off | switch.chainik                         |
      | light  | turn_off | light.yeelink_ceil43_9a4b_light        |
      | light  | turn_off | light.yeelink_ceilc_a6e6_ambient_light |

  Сценарий: Отложенно включить весь свет во всех локациях
    Когда пользователь говорит "включи весь свет через десять секунд"
    Тогда ассистент вызывает сервисы:
      | domain | service | entity_id                              | delay_seconds |
      | light  | turn_on | light.svet_gostinnaia                  | 10            |
      | light  | turn_on | light.svet_kukhnia                     | 10            |
      | light  | turn_on | light.svet_kabinet                     | 10            |
      | light  | turn_on | light.yeelink_ceil43_9a4b_light        | 10            |
      | light  | turn_on | light.yeelink_ceilc_a6e6_ambient_light | 10            |

  Сценарий: Включить весь свет на этаже на время
    Когда пользователь говорит "включи свет на втором этаже на десять секунд"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id                              | delay_seconds |
      | light  | turn_on  | light.svet_gostinnaia                  |               |
      | light  | turn_off | light.svet_gostinnaia                  | 10            |
      | light  | turn_on  | light.svet_kukhnia                     |               |
      | light  | turn_off | light.svet_kukhnia                     | 10            |
      | light  | turn_on  | light.yeelink_ceil43_9a4b_light        |               |
      | light  | turn_off | light.yeelink_ceil43_9a4b_light        | 10            |
      | light  | turn_on  | light.yeelink_ceilc_a6e6_ambient_light |               |
      | light  | turn_off | light.yeelink_ceilc_a6e6_ambient_light | 10            |

  Сценарий: Установить яркость всему свету на этаже
    Когда пользователь говорит "включи свет на втором этаже на пятьдесят процентов"
    Тогда ассистент вызывает сервисы:
      | domain | service | entity_id                              | brightness_pct |
      | light  | turn_on | light.svet_gostinnaia                  | 50             |
      | light  | turn_on | light.svet_kukhnia                     | 50             |
      | light  | turn_on | light.yeelink_ceil43_9a4b_light        | 50             |
      | light  | turn_on | light.yeelink_ceilc_a6e6_ambient_light | 50             |

  Сценарий: Комната колонки применяется вместе с длительностью
    Допустим запрос пришел из комнаты:
      | source_area_id | source_area_name |
      | kukhnia        | Кухня            |
    Когда пользователь говорит "включи свет на десять секунд"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id          | delay_seconds |
      | light  | turn_on  | light.svet_kukhnia |               |
      | light  | turn_off | light.svet_kukhnia | 10            |
