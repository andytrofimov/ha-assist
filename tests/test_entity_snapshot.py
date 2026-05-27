from app import entity_snapshot
from app.api_models import AssistEntity


def test_saves_full_entities_snapshot_as_json(
    tmp_path,
    monkeypatch,
) -> None:
    snapshot_file = tmp_path / "last_entities.json"
    monkeypatch.setattr(entity_snapshot, "LAST_ENTITIES_FILE", snapshot_file)
    entities = [
        AssistEntity.model_validate(
            {
                "entity_id": "light.kitchen",
                "name": "Свет кухня",
                "state": "off",
                "aliases": "свет на кухне",
                "area": "Кухня",
                "attributes": {
                    "brightness": 120,
                    "supported": True,
                },
            },
        ),
    ]

    entity_snapshot.save_entities_snapshot(entities)

    assert snapshot_file.read_text(encoding="utf-8") == """[
  {
    "entity_id": "light.kitchen",
    "name": "Свет кухня",
    "state": "off",
    "aliases": "свет на кухне",
    "area": "Кухня",
    "attributes": {
      "brightness": 120,
      "supported": true
    }
  }
]
"""
