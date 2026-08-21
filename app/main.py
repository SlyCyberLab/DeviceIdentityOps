"""
DeviceIdentityOps - main FastAPI application.

Phase 2 (skeleton): just get the app running, serve the static frontend,
and expose a health check. Real routes (devices, onboarding, offboarding,
audit) get added in later phases.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="DeviceIdentityOps",
    description="IT operations automation - device management, identity lifecycle, and audit trail on top of Microsoft 365 / Entra ID / Intune.",
    version="0.1.0",
)


@app.get("/api/health")
def health_check():
    """Simple liveness check - confirms the API is up and reachable."""
    return {"status": "ok", "service": "deviceidentityops"}


# Serve the static frontend (index.html + any JS/CSS) at the root.
# html=True makes "/" resolve to static/index.html automatically.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
