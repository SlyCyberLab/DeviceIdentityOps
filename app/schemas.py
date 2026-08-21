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
    assigned_user: Optional[str] = None
    os: str
    device_type: Optional[str] = None
    compliance_status: str          # "Compliant" | "Non-Compliant"
    encryption_status: str          # "Encrypted" | "Not Encrypted"
    last_checkin: str
    management_status: str          # "Intune-Managed" | "Seeded (Demo)"


class DeviceDeployRequest(BaseModel):
    serial_number: str
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
