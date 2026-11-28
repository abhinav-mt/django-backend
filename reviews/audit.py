"""
Hash-chain audit log for the AdminReview model.

Ensures tamper-evidence: each AdminReview entry includes the SHA-256 hash
of the previous entry, so editing or deleting any historical record breaks
the cryptographic chain from that point forward.
"""

import hashlib
import json
from datetime import datetime, timezone as dt_timezone
from typing import Any, Optional

from django.db import connection, transaction
from django.utils import timezone

from .models import AdminReview

GENESIS_HASH: str = "0" * 64

# Fixed 64-bit integer constant for PostgreSQL advisory transaction lock
AUDIT_LOCK_KEY: int = 428194829104


def compute_entry_hash(
    prev_hash: str,
    incident_id: int,
    admin_id: int,
    action_taken: str,
    reason_given: Optional[str],
    reviewed_at: datetime,
) -> str:
    """
    Computes deterministic SHA-256 hex digest for an AdminReview entry.

    Pure function with no database access, allowing the future verify_chain
    command to recompute and validate hashes independently.
    """
    if timezone.is_aware(reviewed_at):
        reviewed_at_utc = reviewed_at.astimezone(dt_timezone.utc)
    else:
        reviewed_at_utc = reviewed_at
    reviewed_at_str = reviewed_at_utc.isoformat()

    payload = {
        "action_taken": action_taken,
        "admin_id": int(admin_id),
        "incident_id": int(incident_id),
        "prev_hash": prev_hash,
        "reason_given": reason_given if reason_given is not None else "",
        "reviewed_at": reviewed_at_str,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def append_review(
    incident: Any,
    admin: Any,
    action_taken: str,
    reason_given: str = "",
) -> AdminReview:
    """
    Appends a new AdminReview row in a single atomic transaction.

    Acquires a PostgreSQL advisory transaction lock to serialize concurrent
    appends so that no two reviews obtain the same prev_hash (advisory locks
    protect empty tables where select_for_update is ineffective).
    Explicitly sets reviewed_at before hashing and creates the record in
    a single AdminReview.objects.create(...) insert.
    """
    incident_id = incident.pk if hasattr(incident, "pk") else int(incident)
    admin_id = admin.pk if hasattr(admin, "pk") else int(admin)

    with transaction.atomic():
        # Advisory transaction lock for PostgreSQL to serialize concurrent appends
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s);", [AUDIT_LOCK_KEY])

        # Read latest entry to obtain previous hash, or GENESIS_HASH if table is empty
        latest = AdminReview.objects.order_by("-id").first()
        prev_hash = latest.entry_hash if latest else GENESIS_HASH

        # Explicit timestamp before hashing so stored DB value matches hashed value
        reviewed_at = timezone.now()
        entry_hash = compute_entry_hash(
            prev_hash=prev_hash,
            incident_id=incident_id,
            admin_id=admin_id,
            action_taken=action_taken,
            reason_given=reason_given,
            reviewed_at=reviewed_at,
        )

        create_kwargs = {
            "action_taken": action_taken,
            "reason_given": reason_given,
            "reviewed_at": reviewed_at,
            "prev_hash": prev_hash,
            "entry_hash": entry_hash,
        }
        if hasattr(incident, "pk"):
            create_kwargs["incident"] = incident
        else:
            create_kwargs["incident_id"] = incident_id

        if hasattr(admin, "pk"):
            create_kwargs["admin"] = admin
        else:
            create_kwargs["admin_id"] = admin_id

        return AdminReview.objects.create(**create_kwargs)
