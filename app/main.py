"""
DeviceIdentityOps - main FastAPI application.

Phase 4: routes are now backed by real SQLite persistence. Tables are
created on startup via a lifespan
context manager (the modern replacement for the old @app.on_event hook).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app import logic
from app.schemas import (
    DeviceOut,
    ProcessRequestsResult,
    AuditLogOut,
    OnboardingRequestSubmit,
    OffboardingRequestSubmit,
    SubmitResult,
    IntuneSyncResult,
    IdentityOverview,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if they don't exist. Devices come from the Intune sync.
    Base.metadata.create_all(bind=engine)
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
    """Device dashboard data - devices synced live from Intune."""
    return logic.get_devices(db)


@app.post("/api/devices/refresh-intune", response_model=IntuneSyncResult)
def refresh_intune(db: Session = Depends(get_db)):
    """Sync trigger: pull managed devices from Intune and upsert into the local table."""
    return logic.refresh_intune_devices(db)


# ---------- Identity & Access (IAM) ----------

@app.get("/api/identity", response_model=IdentityOverview)
def identity_overview(db: Session = Depends(get_db)):
    """Live IAM view: tenant users, tool-managed accounts, privileged roles."""
    return logic.get_identity_overview(db)


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
