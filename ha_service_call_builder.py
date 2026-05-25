import json
from typing import Any
from uuid import uuid4


def build_execute_services_tool_call(
    service_items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not service_items:
        return None

    return {
        "id": f"call_{uuid4().hex}",
        "type": "function",
        "function": {
            "name": "execute_services",
            "arguments": json.dumps({"list": service_items}, ensure_ascii=False),
        },
    }


def build_service_item(
    domain: str,
    service: str,
    entity_id: str,
) -> dict[str, Any]:
    return {
        "domain": domain,
        "service": service,
        "service_data": {
            "entity_id": entity_id,
        },
    }
