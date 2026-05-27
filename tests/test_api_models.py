from app.api_models import AssistRequest


def test_assist_request_accepts_areas_and_floors() -> None:
    request = AssistRequest.model_validate(
        {
            "text": "включи свет на первом этаже",
            "entities": [
                {
                    "entity_id": "light.kitchen",
                    "name": "Свет кухня",
                    "state": "off",
                    "aliases": "свет на кухне",
                    "area_id": "kitchen",
                    "area_name": "Кухня",
                    "floor_id": "floor_1",
                    "floor_name": "Первый этаж",
                    "unit_of_measurement": "%",
                    "device_class": "thermostat",
                    "hvac_modes": ["heat", "off"],
                    "attributes": {
                        "temperature": 23.1,
                        "humidity": 50,
                        "wind_speed": 4.2,
                        "forecast": [{"condition": "rainy"}],
                    },
                },
            ],
            "areas": [
                {
                    "area_id": "kitchen",
                    "name": "Кухня",
                    "floor_id": "floor_1",
                    "aliases": "кухня",
                },
            ],
            "floors": [
                {
                    "floor_id": "floor_1",
                    "name": "Первый этаж",
                    "aliases": "первый этаж",
                    "level": 1,
                },
            ],
        },
    )

    assert request.entities[0].floor_name == "Первый этаж"
    assert request.entities[0].unit_of_measurement == "%"
    assert request.entities[0].device_class == "thermostat"
    assert request.entities[0].hvac_modes == ["heat", "off"]
    assert request.entities[0].attributes["temperature"] == 23.1
    assert request.entities[0].attributes["humidity"] == 50
    assert request.entities[0].attributes["wind_speed"] == 4.2
    assert request.entities[0].attributes["forecast"] == [{"condition": "rainy"}]
    assert request.areas[0].name == "Кухня"
    assert request.floors[0].floor_id == "floor_1"
