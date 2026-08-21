# DeviceIdentityOps

Small internal IT operations automation proof-of-concept: device management,
identity lifecycle (onboarding/offboarding), and a unified audit trail, built
on top of Microsoft 365 / Entra ID / Intune / SharePoint.

This isn't a replacement for the Intune admin console or the Entra admin
center - it's the automation and orchestration layer on top of them: one
place that ties device state, identity actions, and access provisioning
together with a single audit trail, which none of those consoles do on
their own.

## Status

Phase 2 - project skeleton. API runs, serves a static frontend, health
check works. No real features yet.

## Stack

- Python + FastAPI
- SQLite (SQLAlchemy)
- Vanilla HTML/CSS/JS frontend
- Microsoft Graph (MSAL, app-only auth)
- Docker

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env       # fill in real values once Phase 8 is reached
uvicorn app.main:app --reload
```

Visit http://localhost:8000 - you should see the DeviceIdentityOps page
showing "API reachable".

## Running in Docker

```bash
docker build -t deviceidentityops .
docker run -p 8000:8000 --env-file .env deviceidentityops
```

## Project structure

```
deviceidentityops/
├── app/
│   ├── main.py          # FastAPI app, routes, mounts static frontend
│   ├── database.py      # SQLite engine/session
│   ├── models.py        # SQLAlchemy: Device, Employee, AuditLog
│   ├── schemas.py       # Pydantic request/response shapes
│   ├── logic.py         # deploy/onboard/offboard/audit workflow logic
│   ├── graph_client.py  # isolated Microsoft Graph auth + calls
│   └── seed_data.py     # seeds mock devices on first run
├── static/
│   └── index.html       # single-page frontend
├── .env.example
├── requirements.txt
├── Dockerfile
└── README.md
```

## Roadmap (build phases)

- [x] Phase 1: MVP specification
- [x] Phase 2: project skeleton
- [ ] Phase 3: FastAPI backend routes
- [ ] Phase 4: SQLite models
- [ ] Phase 5: device dashboard + deployment workflow
- [ ] Phase 6: onboarding/offboarding via SharePoint list front door
- [ ] Phase 7: audit logging
- [ ] Phase 8: Microsoft Graph integration (real Intune device, real Entra ID actions)
- [ ] Phase 9: frontend dashboard
- [ ] Phase 10: Docker
- [ ] Phase 11: testing
- [ ] Phase 12: interview demo prep
