"""
DeviceIdentityOps - main FastAPI application.

Phase 4: routes are now backed by real SQLite persistence. Tables are
created and the device fleet is seeded once on startup, via a lifespan
context manager (the modern replacement for the old @app.on_event hook).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app import logic, seed_data
from app.schemas import (
    DeviceOut,
    DeviceDeployResult,
    ProcessRequestsResult,
    AuditLogOut,
    OnboardingRequestSubmit,
    OffboardingRequestSubmit,
    SubmitResult,
    IntuneSyncResult,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if they don't exist, seed the mock fleet once.
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        seed_data.seed_devices(db)
    finally:
        db.close()
    yield
    # (nothing needed on shutdown for SQLite)


app = FastAPI(
    title="DeviceIdentityOps",
    description="IT operations automation - device management, identity lifecycle, and audit trail on top of Microsoft 365 / Entra ID / Intune.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/api/health")
def health_check():
    """Simple liveness check - confirms the API is up and reachable."""
    return {"status": "ok", "service": "deviceidentityops"}


# ---------- Devices ----------

@app.get("/api/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    """Device dashboard data - seeded fleet now, merged with one real Intune device in Phase 8."""
    return logic.get_devices(db)


@app.delete("/api/devices/{device_id}", response_model=DeviceDeployResult)
def remove_device(device_id: int, db: Session = Depends(get_db)):
    """Removes a device from DeviceIdentityOps's own record and logs it."""
    return logic.remove_device(db, device_id)


@app.post("/api/devices/refresh-intune", response_model=IntuneSyncResult)
def refresh_intune(db: Session = Depends(get_db)):
    """Sync trigger: pull managed devices from Intune and upsert into the local table."""
    return logic.refresh_intune_devices(db)


# ---------- Onboarding / Offboarding ----------

@app.post("/api/onboarding/submit", response_model=SubmitResult)
def submit_onboarding(request: OnboardingRequestSubmit, db: Session = Depends(get_db)):
    """Front door: creates a real Pending item in the SharePoint onboarding list."""
    return logic.submit_onboarding_request(db, request)


@app.post("/api/offboarding/submit", response_model=SubmitResult)
def submit_offboarding(request: OffboardingRequestSubmit, db: Session = Depends(get_db)):
    """Front door: creates a real Pending item in the SharePoint offboarding list."""
    return logic.submit_offboarding_request(db, request)


@app.post("/api/onboarding/process", response_model=ProcessRequestsResult)
def process_onboarding(db: Session = Depends(get_db)):
    """Manual trigger: process Pending items from the SharePoint onboarding list."""
    return logic.process_onboarding_requests(db)


@app.post("/api/offboarding/process", response_model=ProcessRequestsResult)
def process_offboarding(db: Session = Depends(get_db)):
    """Manual trigger: process Pending items from the SharePoint offboarding list."""
    return logic.process_offboarding_requests(db)


# ---------- Audit ----------

@app.get("/api/audit", response_model=list[AuditLogOut])
def get_audit_log(db: Session = Depends(get_db)):
    """Every automation action across devices, onboarding, and offboarding."""
    return logic.get_audit_log(db)


# Serve the static frontend (index.html + any JS/CSS) at the root.
# Mounted last so it doesn't shadow the /api routes above.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
