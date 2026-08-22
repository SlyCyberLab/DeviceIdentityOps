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
        hostname="ENG-LAP-014", serial_number="SN-2026-A001", assigned_user="jane.doe@example.com",
        os="Windows 11", device_type="Laptop", compliance_status="Compliant",
        encryption_status="Encrypted", last_checkin="2026-08-20T14:02:00Z",
        management_status="Seeded (Demo)",
    ),
    dict(
        hostname="SALES-LAP-002", serial_number="SN-2026-A002", assigned_user="marcus.webb@example.com",
        os="Windows 11", device_type="Laptop", compliance_status="Non-Compliant",
        encryption_status="Not Encrypted", last_checkin="2026-08-18T09:15:00Z",
        management_status="Seeded (Demo)",
    ),
]


def seed_devices(db: Session) -> None:
    if db.query(Device).count() > 0:
        return  # already seeded, don't duplicate
    db.add_all(Device(**row) for row in _SEED_DEVICES)
    db.commit()
