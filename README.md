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

Phases 1-5, 7, 9, and most of 6 are done. The device dashboard, deployment
workflow, audit trail, and full frontend are real and working against
SQLite. Onboarding/offboarding logic is fully written and wired to a
Microsoft Graph client seam - it just reports "not configured" until
Phase 8 supplies a real Entra ID app registration and SharePoint list IDs.

That's the one remaining step that needs actual Azure/Entra work outside
this codebase: standing up the Microsoft 365 Business Premium trial,
registering an app, and enrolling one real VM in Intune.

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

SQLite lives inside the container by default - fine for demo purposes, but
mount a volume if you want data to survive a container restart:

```bash
docker run -p 8000:8000 --env-file .env -v $(pwd)/data:/app/data deviceidentityops
```

(and set `DATABASE_URL=sqlite:////app/data/deviceidentityops.db` in `.env`)

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
- [x] Phase 3: FastAPI backend routes
- [x] Phase 4: SQLite models
- [x] Phase 5: device dashboard + deployment workflow (with duplicate-serial validation)
- [x] Phase 6: onboarding/offboarding logic - fully written, wired to a Graph
      client seam that reports "not configured" until Phase 8
- [x] Phase 7: audit logging
- [ ] **Phase 8: Microsoft Graph integration - needs a Business Premium
      tenant, an Entra ID app registration, and one real Intune-enrolled
      VM. This is the next step, and it happens outside this codebase.**
- [x] Phase 9: frontend dashboard (health bar, device table, detail panel,
      deploy form, onboarding/offboarding triggers, audit log)
- [x] Phase 10: Docker (build-tested structure; not build-verified in this
      environment - verify on your own Docker server)
- [ ] Phase 11: testing
- [ ] Phase 12: interview demo prep

## What Phase 8 needs before it can be built

1. Microsoft 365 Business Premium 30-day trial (cloud-only tenant)
2. One Entra ID app registration with application permissions:
   `User.ReadWrite.All`, `Group.ReadWrite.All`, `Sites.ReadWrite.All`,
   `DeviceManagementManagedDevices.Read.All`, `Mail.Send` - admin consent
   granted on each
3. A client secret, dropped into `.env` as `TENANT_ID` / `CLIENT_ID` /
   `CLIENT_SECRET`
4. One SharePoint site with two lists (New Hire Requests, Offboarding
   Requests), matching the columns from the Identity Lifecycle Automation
   project
5. One Proxmox VM enrolled in Intune, so `get_managed_devices()` has a real
   device to return

Once those exist, Phase 8 is filling in the `NotImplementedError` bodies in
`graph_client.py` - nothing in `main.py` or `logic.py` needs to change.
