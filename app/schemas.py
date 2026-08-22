"""
Pydantic request/response shapes for the API.

These define the contract each endpoint promises - what a request must
contain, what a response will look like - independent of how the data is
actually stored. Phase 4 wires these to real SQLAlchemy models; for now
main.py returns data that matches these shapes so the API is testable
end to end before persistence exists.
"""

from pydantic import BaseModel
from typing import Optional


# ---------- Devices ----------

class DeviceOut(BaseModel):
    id: int
    hostname: str
    serial_number: Optional[str] = None
    assigned_user: Optional[str] = None
    os: str
    device_type: Optional[str] = None
    compliance_status: str          # "Compliant" | "Non-Compliant"
    encryption_status: str          # "Encrypted" | "Not Encrypted"
    last_checkin: str
    management_status: str          # "Intune-Managed" | "Seeded (Demo)"


class ProcessRequestsResult(BaseModel):
    processed_count: int
    results: list[str]


# ---------- Audit ----------

class AuditLogOut(BaseModel):
    id: int
    timestamp: str
    action_type: str         # "DEVICE_DEPLOYMENT" | "ONBOARDING" | "OFFBOARDING"
    target: str
    result: str               # "SUCCESS" | "FAILED"


# ---------- Request submission (the front door forms) ----------

class OnboardingRequestSubmit(BaseModel):
    first_name: str
    last_name: str
    department: str
    manager_email: str
    start_date: str   # YYYY-MM-DD from a <input type="date">
    license: str = "Business Premium"


class OffboardingRequestSubmit(BaseModel):
    upn: str
    display_name: str
    manager_email: str
    last_working_day: str  # YYYY-MM-DD


class SubmitResult(BaseModel):
    success: bool
    message: str


class IntuneSyncResult(BaseModel):
    success: bool
    synced_count: int
    message: str


# ---------- Identity & Access (IAM) ----------

class IdentityUser(BaseModel):
    display_name: str
    upn: str
    enabled: bool
    licensed: bool
    department: Optional[str] = None
    managed_by_tool: bool  # True if this tool provisioned or offboarded the account


class PrivilegedRole(BaseModel):
    role_name: str
    members: list[str]


class IdentityOverview(BaseModel):
    users: list[IdentityUser]
    privileged_roles: list[PrivilegedRole]
    roles_available: bool          # False when RoleManagement.Read.Directory isn't granted
    observations: list[str]
