import json
from pathlib import Path

from app.api_models import AssistEntity

# Последний список entity нужен только для локальной диагностики.
LAST_ENTITIES_FILE = Path(__file__).resolve().parent.parent / "last_entities.json"


def save_entities_snapshot(entities: list[AssistEntity]) -> None:
    entity_items = [
        entity.model_dump(mode="json")
        for entity in entities
    ]
    LAST_ENTITIES_FILE.write_text(
        json.dumps(entity_items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
