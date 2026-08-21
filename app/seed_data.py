"""
Seeds a mock device fleet into SQLite on first run, so the dashboard looks
like a real environment even though only one device (added in Phase 8) is
a genuinely Intune-enrolled VM. Runs once - if the devices table already
has rows, this is a no-op.
"""

from sqlalchemy.orm import Session
from app.models import Device

_SEED_DEVICES = [
    dict(
        hostname="ENG-LAP-014", assigned_user="jane.doe@example.com",
        os="Windows 11", compliance_status="Compliant",
        encryption_status="Encrypted", last_checkin="2026-08-20T14:02:00Z",
        management_status="Seeded (Demo)",
    ),
    dict(
        hostname="SALES-LAP-002", assigned_user="marcus.webb@example.com",
        os="Windows 11", compliance_status="Non-Compliant",
        encryption_status="Not Encrypted", last_checkin="2026-08-18T09:15:00Z",
        management_status="Seeded (Demo)",
    ),
    dict(
        hostname="OPS-LAP-007", assigned_user="priya.raman@example.com",
        os="Windows 11", compliance_status="Compliant",
        encryption_status="Encrypted", last_checkin="2026-08-20T08:47:00Z",
        management_status="Seeded (Demo)",
    ),
    dict(
        hostname="HR-LAP-003", assigned_user="carlos.mendez@example.com",
        os="Windows 11", compliance_status="Compliant",
        encryption_status="Encrypted", last_checkin="2026-08-19T16:30:00Z",
        management_status="Seeded (Demo)",
    ),
    dict(
        hostname="ENG-LAP-021", assigned_user="alex.chen@example.com",
        os="Windows 11", compliance_status="Non-Compliant",
        encryption_status="Not Encrypted", last_checkin="2026-08-15T11:05:00Z",
        management_status="Seeded (Demo)",
    ),
    dict(
        hostname="FIN-LAP-005", assigned_user="dana.reyes@example.com",
        os="Windows 11", compliance_status="Compliant",
        encryption_status="Encrypted", last_checkin="2026-08-20T09:58:00Z",
        management_status="Seeded (Demo)",
    ),
]


def seed_devices(db: Session) -> None:
    if db.query(Device).count() > 0:
        return  # already seeded, don't duplicate
    db.add_all(Device(**row) for row in _SEED_DEVICES)
    db.commit()
