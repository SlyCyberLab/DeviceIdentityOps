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


class DeviceDeployRequest(BaseModel):
    serial_number: str
    hostname: str          # the name IT is assigning during imaging - mirrors the MDT PUT pattern
    assigned_user: str
    department: str
    device_type: str


class DeviceDeployResult(BaseModel):
    success: bool
    message: str
    policy_assigned: Optional[str] = None
    dry_run: bool


# ---------- Onboarding / Offboarding ----------

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
