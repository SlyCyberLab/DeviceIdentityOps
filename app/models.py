"""
SQLAlchemy models: Device, Employee, AuditLog.

Kept deliberately small - just the columns the dashboard and workflows
actually use. Employee exists mainly as a record of what onboarding
created; the SharePoint list (Phase 6) is the real request record, this
table is DeviceIdentityOps's own copy of what it acted on.
"""

from sqlalchemy import Column, Integer, String
from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String, nullable=False)
    assigned_user = Column(String, nullable=True)
    os = Column(String, nullable=False)
    device_type = Column(String, nullable=True)  # Laptop, Desktop, etc. - distinct from OS
    compliance_status = Column(String, nullable=False, default="Unknown")
    encryption_status = Column(String, nullable=False, default="Unknown")
    last_checkin = Column(String, nullable=True)
    # "Intune-Managed" for the one real enrolled VM, "Seeded (Demo)" for the
    # rest of the fleet, "Deployed (Dry-Run)" for anything created through
    # the deployment workflow.
    management_status = Column(String, nullable=False, default="Seeded (Demo)")


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    department = Column(String, nullable=False)
    manager_email = Column(String, nullable=False)
    upn = Column(String, nullable=True)          # set once the real Entra ID user is created (Phase 8)
    status = Column(String, nullable=False, default="Pending")  # Pending | Completed | Failed


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(String, nullable=False)
    action_type = Column(String, nullable=False)   # DEVICE_DEPLOYMENT | ONBOARDING | OFFBOARDING
    target = Column(String, nullable=False)
    result = Column(String, nullable=False)         # SUCCESS | FAILED
