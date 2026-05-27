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
      | gostinaia | Гостиная | vtoroi   |         |
      | kukhnia   | Кухня    | vtoroi   |         |
      | kabinet   | Кабинет  | tretii   |         |
    И доступны этажи:
      | floor_id | name   | aliases | level |
      | vtoroi   | Второй |         | 2     |
      | tretii   | Третий |         | 3     |

  Сценарий: Использовать комнату колонки если комната не указана
    Допустим запрос пришел из комнаты:
      | source_area_id | source_area_name |
      | kukhnia        | Кухня            |
    Когда пользователь говорит "выключи свет"
    Тогда ассистент вызывает сервисы:
      | domain | service  | entity_id          |
      | light  | turn_off | light.svet_kukhnia |

  Сценарий: Выключить весь свет на этаже
    Когда пользователь говорит "выключи свет на втором этаже"
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
