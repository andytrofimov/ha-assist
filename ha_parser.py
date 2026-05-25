import csv
import io

from pydantic import BaseModel

from api_models import ChatMessage


class HaObject(BaseModel):
    entity_id: str
    name: str
    state: str
    aliases: str


def parse_ha_objects(messages: list[ChatMessage]) -> list[HaObject]:
    system_message = next(
        (message for message in messages if message.role == "system" and message.content),
        None,
    )
    if system_message is None:
        return []

    csv_text = extract_csv_block(system_message.content)
    if csv_text is None:
        return []

    reader = csv.DictReader(io.StringIO(csv_text))
    return [
        HaObject(
            entity_id=row.get("entity_id", ""),
            name=row.get("name", ""),
            state=row.get("state", ""),
            aliases=row.get("aliases", ""),
        )
        for row in reader
        if row.get("entity_id")
    ]


def extract_csv_block(content: str) -> str | None:
    marker = "```csv"
    start = content.find(marker)
    if start == -1:
        return None

    start += len(marker)
    end = content.find("```", start)
    if end == -1:
        return None

    return content[start:end].strip()
