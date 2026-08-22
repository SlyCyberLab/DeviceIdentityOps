"""
Seed data - intentionally empty as of the live-Intune milestone.

Earlier phases seeded a mock demo fleet so the dashboard had something to
show before real Graph integration existed. Once the real Intune sync came
online, the mock rows undercut the "everything on screen is real" story,
so the fleet now consists solely of devices synced from Intune.
"""

from sqlalchemy.orm import Session


def seed_if_empty(db: Session) -> None:
    """No-op: devices come exclusively from the Intune sync now."""
    return
