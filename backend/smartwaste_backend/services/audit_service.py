"""Append-only audit trail for user actions (who changed what, from which request)."""

import uuid

from ..core.common import utcnow


def record(database, *, actor_id, action, entity_type, entity_id, summary, request_id=None,
           session=None):
    key = f"{action}:{entity_id}:{uuid.uuid4().hex[:12]}"
    database.audit_logs.insert_one({
        "_id": f"aud-{uuid.uuid4().hex}", "event_key": key, "actor_id": actor_id,
        "action": action, "entity_type": entity_type, "entity_id": entity_id,
        "source_message_id": None, "occurred_at": utcnow(), "summary": summary[:1500],
        "request_id": request_id,
    }, session=session)
