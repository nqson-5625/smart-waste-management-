"""Append-only audit trail: who changed what, when, from which request or message.

Every audit write in the backend goes through ``record``.
"""

import uuid

from ..core.common import utcnow


def record(database, *, actor_id, action, entity_type, entity_id, summary, request_id=None,
           source_message_id=None, event_key=None, occurred_at=None, session=None):
    """Insert one audit entry.

    Pass a stable ``event_key`` (for example ``alert_open:<alert id>``) when the same event
    could be recorded twice; the unique index on event_key then rejects the duplicate.
    Without it a random key is used, so every call is a new entry.
    """
    key = event_key or f"{action}:{entity_id}:{uuid.uuid4().hex[:12]}"
    database.audit_logs.insert_one({
        "_id": f"aud-{uuid.uuid4().hex}", "event_key": key, "actor_id": actor_id,
        "action": action, "entity_type": entity_type, "entity_id": entity_id,
        "source_message_id": source_message_id, "occurred_at": occurred_at or utcnow(),
        "summary": summary[:1500], "request_id": request_id,
    }, session=session)
