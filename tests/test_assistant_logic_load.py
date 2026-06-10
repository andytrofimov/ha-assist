from statistics import mean
from time import perf_counter
from typing import Any

from ha_assist_core.assistant_logic import build_assist_result
from ha_assist_core.ha_parser import HaObject

REPEAT_COUNT = 5
USER_REQUESTS = (
    "включи свет в кухне",
    "выключи свет везде",
    "включи кондиционеры везде",
    "выключи чайник на кухне",
    "открой шторы в спальне",
    "какая температура в гостиной",
    "включи весь свет на втором этаже",
    "поставь свет в кабинете на 50 процентов",
    "включи вентилятор в спальне на десять минут",
    "добавь в список покупок молоко и хлеб",
    "пожалуйста включи весь свет на жилом этаже и поставь его на пятьдесят процентов",
    "через десять минут выключи весь свет на втором этаже",
    "включи подсветку в гостиной на двадцать пять процентов на десять минут",
    "поставь кондиционер в спальне на двадцать два градуса",
    "сколько сейчас покупок",
    "перезапуск zigbee",
    "расскажи анекдот про умный дом",
    "как включить свет в игре",
    "почему кондиционер называют сплит системой",
    "что делать если дома внезапно пропал интернет",
)


def make_entity(
        entity_id: str,
        name: str,
        state: str,
        area_id: str,
        area_name: str,
        floor_id: str,
        floor_name: str,
        aliases: str = "",
        unit_of_measurement: str | None = None,
        device_class: str | None = None,
        hvac_modes: list[str] | None = None,
) -> HaObject:
    return HaObject(
        entity_id=entity_id,
        name=name,
        state=state,
        aliases=aliases,
        area_id=area_id,
        area_name=area_name,
        floor_id=floor_id,
        floor_name=floor_name,
        unit_of_measurement=unit_of_measurement,
        device_class=device_class,
        hvac_modes=hvac_modes or [],
        attributes={},
    )


def smart_home_fixture() -> tuple[list[HaObject], list[dict[str, Any]], list[dict[str, Any]]]:
    areas = [
        {"area_id": "gostinaia", "name": "Гостиная", "floor_id": "vtoroi", "aliases": "зал"},
        {"area_id": "kukhnia", "name": "Кухня", "floor_id": "vtoroi", "aliases": ""},
        {"area_id": "spalnia", "name": "Спальня", "floor_id": "vtoroi", "aliases": ""},
        {"area_id": "kabinet", "name": "Кабинет", "floor_id": "tretii", "aliases": ""},
        {"area_id": "vannaia", "name": "Ванная", "floor_id": "pervyi", "aliases": ""},
        {"area_id": "koridor", "name": "Коридор", "floor_id": "pervyi", "aliases": ""},
        {"area_id": "detskaia", "name": "Детская", "floor_id": "tretii", "aliases": ""},
        {"area_id": "garazh", "name": "Гараж", "floor_id": "pervyi", "aliases": ""},
    ]
    floors = [
        {"floor_id": "pervyi", "name": "Первый", "aliases": "нижний", "level": 1},
        {"floor_id": "vtoroi", "name": "Второй", "aliases": "жилой", "level": 2},
        {"floor_id": "tretii", "name": "Третий", "aliases": "верхний", "level": 3},
    ]
    area_by_id = {area["area_id"]: area for area in areas}
    floor_by_id = {floor["floor_id"]: floor for floor in floors}

    entities: list[HaObject] = [
        make_entity("todo.shopping", "Список покупок", "0", "", "", "", "", aliases="напомни купить"),
        make_entity("scene.kino", "Сцена кино", "off", "gostinaia", "Гостиная", "vtoroi", "Второй"),
        make_entity("button.restart_zigbee", "Перезапуск Zigbee", "off", "kabinet", "Кабинет", "tretii", "Третий"),
    ]
    for index, area in enumerate(areas, start=1):
        floor = floor_by_id[area["floor_id"]]
        entities.extend(
            [
                make_entity(
                    f"light.svet_{area['area_id']}",
                    f"Свет {area['name']}",
                    "off",
                    area["area_id"],
                    area["name"],
                    floor["floor_id"],
                    floor["name"],
                ),
                make_entity(
                    f"light.podsvetka_{area['area_id']}",
                    f"Подсветка {area['name']}",
                    "off",
                    area["area_id"],
                    area["name"],
                    floor["floor_id"],
                    floor["name"],
                ),
                make_entity(
                    f"switch.rozetka_{area['area_id']}",
                    f"Розетка {area['name']}",
                    "off",
                    area["area_id"],
                    area["name"],
                    floor["floor_id"],
                    floor["name"],
                ),
                make_entity(
                    f"sensor.temperature_{area['area_id']}",
                    f"Температура {area['name']}",
                    str(20 + index),
                    area["area_id"],
                    area["name"],
                    floor["floor_id"],
                    floor["name"],
                    unit_of_measurement="°C",
                    device_class="temperature",
                ),
            ],
        )

    entities.extend(
        [
            make_entity("switch.chainik", "Чайник", "off", "kukhnia", "Кухня", "vtoroi", "Второй"),
            make_entity(
                "cover.shtory_spalnia",
                "Шторы спальня",
                "closed",
                "spalnia",
                "Спальня",
                "vtoroi",
                "Второй",
                aliases="шторы",
            ),
            make_entity(
                "climate.konditsioner_spalnia",
                "Кондиционер спальня",
                "cool",
                "spalnia",
                "Спальня",
                "vtoroi",
                "Второй",
                hvac_modes=["cool", "heat", "off"],
            ),
            make_entity(
                "climate.konditsioner_kabinet",
                "Кондиционер кабинет",
                "cool",
                "kabinet",
                "Кабинет",
                "tretii",
                "Третий",
                hvac_modes=["cool", "heat", "off"],
            ),
            make_entity(
                "fan.ventiliator_spalnia",
                "Вентилятор спальня",
                "off",
                "spalnia",
                "Спальня",
                "vtoroi",
                "Второй",
            ),
        ],
    )

    for index in range(10):
        area = areas[index % len(areas)]
        floor = floor_by_id[area["floor_id"]]
        entities.append(
            make_entity(
                f"binary_sensor.motion_{index}",
                f"Движение {area['name']} {index}",
                "off",
                area["area_id"],
                area["name"],
                floor["floor_id"],
                floor["name"],
                device_class="motion",
            ),
        )

    assert len(entities) == 50
    assert set(area_by_id) >= {"kukhnia", "spalnia", "gostinaia", "kabinet"}
    return entities, areas, floors


def test_assistant_logic_load(capsys: Any) -> None:
    ha_objects, areas, floors = smart_home_fixture()
    timings_by_request: dict[str, list[float]] = {request: [] for request in USER_REQUESTS}
    started_all_at = perf_counter()

    for request in USER_REQUESTS:
        for _ in range(REPEAT_COUNT):
            started_at = perf_counter()
            build_assist_result(
                request,
                ha_objects,
                areas=areas,
                floors=floors,
                source_area_id=None,
                source_area_name=None,
                source_floor_id=None,
                source_floor_name=None,
                previous_exchange=None,
            )
            elapsed_ms = (perf_counter() - started_at) * 1000
            timings_by_request[request].append(elapsed_ms)

    total_measurements = sum(len(values) for values in timings_by_request.values())
    total_elapsed_ms = (perf_counter() - started_all_at) * 1000
    assert total_measurements == len(USER_REQUESTS) * REPEAT_COUNT

    report_lines = ["assistant_logic load timings, ms:"]
    for request, values in timings_by_request.items():
        report_lines.append(
            f"{request}: avg={mean(values):.2f}, min={min(values):.2f}, max={max(values):.2f}",
        )
    report_lines.append(
        f"measurements={total_measurements}, requests={len(USER_REQUESTS)}, repeats={REPEAT_COUNT}",
    )
    report_lines.append(
        f"overall: avg={mean(value for values in timings_by_request.values() for value in values):.2f}",
    )
    report_lines.append(f"total: {total_elapsed_ms:.2f}")
    with capsys.disabled():
        print("\n" + "\n".join(report_lines))
