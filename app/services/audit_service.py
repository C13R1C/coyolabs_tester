import json

from app.extensions import db
from app.models.logbook import LogbookEvent


def _normalize_metadata(metadata: dict | None) -> dict:
    if not isinstance(metadata, dict):
        return {}
    return dict(metadata)


def log_event(*, module: str, action: str, user_id: int | None = None, entity_label: str | None = None,
              description: str | None = None, metadata: dict | None = None, material_id: int | None = None) -> None:
    normalized_metadata = _normalize_metadata(metadata)
    evt = LogbookEvent(
        user_id=user_id,
        material_id=material_id,
        action=action,
        module=(module or "").strip().upper() or None,
        entity_label=entity_label,
        description=description,
        metadata_json=json.dumps(normalized_metadata, ensure_ascii=False),
    )
    db.session.add(evt)
