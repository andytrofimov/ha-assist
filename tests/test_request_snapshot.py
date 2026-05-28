import json

from app.api_models import AssistRequest
from app import main


def test_saves_full_assist_request_snapshot(
    tmp_path,
    monkeypatch,
) -> None:
    snapshot_file = tmp_path / "last_assist_request.json"
    monkeypatch.setattr(main, "LAST_ASSIST_REQUEST_FILE", snapshot_file)
    request = AssistRequest.model_validate(
        {
            "text": "включи свет на первом этаже",
            "language": "ru",
            "conversation_id": "conversation-1",
            "source_device_id": "media_player.kitchen_speaker",
            "source_area_id": "kitchen",
            "source_area_name": "Кухня",
            "source_floor_id": "floor_1",
            "source_floor_name": "Первый этаж",
            "entities": [
                {
                    "entity_id": "light.kitchen",
                    "name": "Свет кухня",
                    "state": "off",
                    "aliases": "свет на кухне",
                    "area_name": "Кухня",
                    "floor_name": "Первый этаж",
                },
            ],
            "areas": [
                {
                    "area_id": "kitchen",
                    "name": "Кухня",
                    "floor_id": "floor_1",
                },
            ],
            "floors": [
                {
                    "floor_id": "floor_1",
                    "name": "Первый этаж",
                },
            ],
        },
    )

    main.save_assist_request_snapshot(request)

    assert json.loads(snapshot_file.read_text(encoding="utf-8")) == {
        "text": "включи свет на первом этаже",
        "language": "ru",
        "conversation_id": "conversation-1",
        "entities": [
            {
                "entity_id": "light.kitchen",
                "name": "Свет кухня",
                "state": "off",
                "aliases": "свет на кухне",
                "area_name": "Кухня",
                "floor_name": "Первый этаж",
            },
        ],
        "areas": [
            {
                "area_id": "kitchen",
                "name": "Кухня",
                "floor_id": "floor_1",
                "aliases": "",
            },
        ],
        "floors": [
            {
                "floor_id": "floor_1",
                "name": "Первый этаж",
                "aliases": "",
            },
        ],
        "source_device_id": "media_player.kitchen_speaker",
        "source_area_id": "kitchen",
        "source_area_name": "Кухня",
        "source_floor_id": "floor_1",
        "source_floor_name": "Первый этаж",
    }
