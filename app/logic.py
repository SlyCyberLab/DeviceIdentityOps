"""
Core workflow logic: device deployment, onboarding, offboarding, audit writes.

Kept separate from main.py's route handlers on purpose - main.py deals with
HTTP, this module deals with "what actually happens" (validate, act, write
to AuditLog). Keeping the dry-run safety default here, rather than at the
API boundary, is a deliberate choice: the safety behavior lives with the
business logic, not the transport layer.

Phase 4: backed by real SQLite persistence via models.py.
Phase 8 wires device/onboarding/offboarding actions to real Microsoft Graph
calls via graph_client.py, still behind the same dry-run flag.
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app import graph_client
from app import monday_client
from app.models import Device as DeviceModel, Employee as EmployeeModel, AuditLog as AuditLogModel
from app.schemas import (
    DeviceOut,
    ProcessRequestsResult,
    AuditLogOut,
    OnboardingRequestSubmit,
    OffboardingRequestSubmit,
    SubmitResult,
    IntuneSyncResult,
    IdentityUser,
    PrivilegedRole,
    IdentityOverview,
)

# Safety default: real device/identity actions stay simulated until this is
# explicitly flipped in a controlled environment (see .env.example).
DRY_RUN = True

# Department -> Intune policy group. Deliberately simple - a real system
# would look this up from a policy table, but the rule itself isn't the
# point of the demo.


def _write_audit(db: Session, action_type: str, target: str, result: str) -> None:
    entry = AuditLogModel(
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        action_type=action_type,
        target=target,
        result=result,
    )
    db.add(entry)
    db.commit()
    # Mirror to Monday.com if configured - single integration point, so every
    # audited action surfaces on the board with no per-call wiring. No-op when
    # MONDAY_API_TOKEN isn't set, and never raises into the caller.
    monday_client.post_event(action_type, target, result)


def get_devices(db: Session) -> list[DeviceOut]:
    devices = db.query(DeviceModel).order_by(DeviceModel.id).all()
    return [
        DeviceOut(
            id=d.id,
            hostname=d.hostname,
            serial_number=d.serial_number,
            assigned_user=d.assigned_user,
            os=d.os,
            device_type=d.device_type,
            compliance_status=d.compliance_status,
            encryption_status=d.encryption_status,
            last_checkin=d.last_checkin,
            management_status=d.management_status,
        )
        for d in devices
    ]


def process_onboarding_requests(db: Session) -> ProcessRequestsResult:
    """
    Reads Pending items from the SharePoint onboarding list and, for each:
    create_user -> set_usage_location -> assign_license -> add_to_group
    (SharePoint access) -> send_mail -> write back Completed. Falls back to
    a clear "not configured" message until Phase 8 supplies real Graph
    credentials - the loop below is otherwise the real implementation.
    """
    if not graph_client.is_configured():
        return ProcessRequestsResult(
            processed_count=0,
            results=["Microsoft Graph not configured yet - set TENANT_ID/CLIENT_ID/CLIENT_SECRET in .env (Phase 8)."],
        )

    try:
        pending = graph_client.get_pending_onboarding_requests()
    except Exception as exc:
        return ProcessRequestsResult(
            processed_count=0,
            results=[f"Failed to read pending requests from SharePoint: {exc}"],
        )

    results = []
    for req in pending:
        try:
            user = graph_client.create_user(req["display_name"], req["department"])
            graph_client.set_usage_location(user["id"])
            graph_client.assign_license(user["id"], sku_id=req.get("license_sku"))
            graph_client.add_to_group(user["id"], group_id=req.get("access_group"))
            graph_client.send_mail(
                to_address=req["manager_email"],
                subject=f"New hire account provisioned: {req['display_name']}",
                body=(
                    f"Hello,\n"
                    f"\n"
                    f"The account for the new employee has been provisioned.\n"
                    f"\n"
                    f"Employee:      {req['display_name']}\n"
                    f"Username:      {user['userPrincipalName']}\n"
                    f"Department:    {req['department']}\n"
                    f"Start date:    {req.get('start_date', '')}\n"
                    f"\n"
                    f"Temporary password: {user.get('_temp_password', '(not available)')}\n"
                    f"\n"
                    f"Microsoft 365 portal: https://www.office.com\n"
                    f"\n"
                    f"The employee will be required to change their password at first sign-in,\n"
                    f"and must complete MFA registration during their first login.\n"
                    f"\n"
                    f"Please share these credentials with the new hire securely on their start\n"
                    f"date. Do not forward this email externally.\n"
                ),
            )
            db.add(EmployeeModel(
                name=req["display_name"], department=req["department"],
                manager_email=req["manager_email"], upn=user["userPrincipalName"],
                status="Completed",
            ))
            # The real provisioning (user, license, email) already succeeded by this
            # point - a failure writing the status back to SharePoint shouldn't be
            # reported as an onboarding failure, just noted separately.
            try:
                graph_client.write_back_status(req["list_id"], req["item_id"], "Completed", upn=user["userPrincipalName"])
                writeback_note = ""
            except Exception as wb_exc:
                writeback_note = f" (SharePoint status write-back failed: {wb_exc})"
            _write_audit(db, "ONBOARDING", req["display_name"], "SUCCESS")
            results.append(f"{req['display_name']}: provisioned{writeback_note}")
        except Exception as exc:
            _write_audit(db, "ONBOARDING", req.get("display_name", "unknown"), "FAILED")
            results.append(f"{req.get('display_name', 'unknown')}: failed - {exc}")

    db.commit()
    return ProcessRequestsResult(processed_count=len(pending), results=results)


def process_offboarding_requests(db: Session) -> ProcessRequestsResult:
    """
    Mirror of onboarding: disable_user -> invalidate_sessions -> remove_license
    -> remove_from_group -> send_mail -> write back Completed. Same
    "not configured" fallback until Phase 8.
    """
    if not graph_client.is_configured():
        return ProcessRequestsResult(
            processed_count=0,
            results=["Microsoft Graph not configured yet - set TENANT_ID/CLIENT_ID/CLIENT_SECRET in .env (Phase 8)."],
        )

    try:
        pending = graph_client.get_pending_offboarding_requests()
    except Exception as exc:
        return ProcessRequestsResult(
            processed_count=0,
            results=[f"Failed to read pending requests from SharePoint: {exc}"],
        )

    results = []
    for req in pending:
        try:
            graph_client.disable_user(req["user_id"])
            graph_client.invalidate_sessions(req["user_id"])
            graph_client.remove_license(req["user_id"], sku_id=req.get("license_sku"))
            graph_client.remove_from_group(req["user_id"], group_id=req.get("access_group"))
            offboard_name = req["display_name"] or req["upn"]
            graph_client.send_mail(
                to_address=req["manager_email"],
                subject=f"Offboarding completed: {offboard_name}",
                body=(
                    f"Hello,\n"
                    f"\n"
                    f"Offboarding has been completed for the following employee.\n"
                    f"\n"
                    f"Employee:          {offboard_name}\n"
                    f"Username:          {req['upn']}\n"
                    f"Last working day:  {req.get('last_working_day', '')}\n"
                    f"\n"
                    f"Actions taken:\n"
                    f"  - Account sign-in disabled\n"
                    f"  - All active sessions revoked\n"
                    f"  - License removed and reclaimed\n"
                    f"\n"
                    f"If this offboarding was submitted in error, contact IT immediately.\n"
                ),
            )
            employee = db.query(EmployeeModel).filter(EmployeeModel.upn == req["upn"]).first()
            if employee:
                employee.status = "Offboarded"
            try:
                graph_client.write_back_status(req["list_id"], req["item_id"], "Completed")
                writeback_note = ""
            except Exception as wb_exc:
                writeback_note = f" (SharePoint status write-back failed: {wb_exc})"
            _write_audit(db, "OFFBOARDING", req["display_name"], "SUCCESS")
            results.append(f"{req['display_name']}: offboarded{writeback_note}")
        except Exception as exc:
            _write_audit(db, "OFFBOARDING", req.get("display_name", "unknown"), "FAILED")
            results.append(f"{req.get('display_name', 'unknown')}: failed - {exc}")

    db.commit()
    return ProcessRequestsResult(processed_count=len(pending), results=results)


def get_audit_log(db: Session) -> list[AuditLogOut]:
    entries = db.query(AuditLogModel).order_by(AuditLogModel.id.desc()).all()
    return [
        AuditLogOut(
            id=e.id,
            timestamp=e.timestamp,
            action_type=e.action_type,
            target=e.target,
            result=e.result,
        )
        for e in entries
    ]


def submit_onboarding_request(db: Session, request: OnboardingRequestSubmit) -> SubmitResult:
    """
    Creates a real Pending item in the New Hire Requests SharePoint list.
    This is the front door - a manager (or, for the demo, you) fills out
    this form instead of a Power Apps form; either way the item lands in
    the same SharePoint list, which is what Process Requests actually reads.
    """
    if not graph_client.is_configured():
        return SubmitResult(
            success=False,
            message="Microsoft Graph not configured yet - set TENANT_ID/CLIENT_ID/CLIENT_SECRET in .env (Phase 8).",
        )
    try:
        graph_client.create_onboarding_request({
            "Title": f"{request.first_name} {request.last_name}",
            "FirstName": request.first_name,
            "LastName": request.last_name,
            "Department": request.department,
            "ManagerEmail": request.manager_email,
            "StartDate": f"{request.start_date}T00:00:00Z",
            "License": request.license,
        })
        _write_audit(db, "ONBOARDING_REQUEST_SUBMITTED", f"{request.first_name} {request.last_name}", "SUCCESS")
        return SubmitResult(success=True, message=f"Request submitted for {request.first_name} {request.last_name}.")
    except Exception as exc:
        _write_audit(db, "ONBOARDING_REQUEST_SUBMITTED", f"{request.first_name} {request.last_name}", "FAILED")
        return SubmitResult(success=False, message=f"Failed to submit request: {exc}")


def submit_offboarding_request(db: Session, request: OffboardingRequestSubmit) -> SubmitResult:
    """Creates a real Pending item in the Offboarding Requests SharePoint list."""
    if not graph_client.is_configured():
        return SubmitResult(
            success=False,
            message="Microsoft Graph not configured yet - set TENANT_ID/CLIENT_ID/CLIENT_SECRET in .env (Phase 8).",
        )
    try:
        graph_client.create_offboarding_request({
            "Title": request.display_name,
            "UPN": request.upn,
            "DisplayName": request.display_name,
            "ManagerEmail": request.manager_email,
            "LastWorkingDay": f"{request.last_working_day}T00:00:00Z",
        })
        _write_audit(db, "OFFBOARDING_REQUEST_SUBMITTED", request.display_name, "SUCCESS")
        return SubmitResult(success=True, message=f"Offboarding request submitted for {request.display_name}.")
    except Exception as exc:
        _write_audit(db, "OFFBOARDING_REQUEST_SUBMITTED", request.display_name, "FAILED")
        return SubmitResult(success=False, message=f"Failed to submit request: {exc}")


def refresh_intune_devices(db: Session) -> IntuneSyncResult:
    """
    Pulls managed devices from Intune via Graph and upserts them into the
    local device table (matched on Intune device id). Cached-with-manual-
    refresh by design: the dashboard always renders instantly from the last
    sync, and this is the sync trigger - the same pattern real inventory
    tools use, rather than calling the MDM API on every page view.
    """
    if not graph_client.is_configured():
        return IntuneSyncResult(success=False, synced_count=0,
                                message="Microsoft Graph not configured yet.")
    try:
        intune_devices = graph_client.get_managed_devices()
    except Exception as exc:
        return IntuneSyncResult(success=False, synced_count=0,
                                message=f"Failed to read from Intune: {exc}")

    compliance_map = {
        "compliant": "Compliant",
        "noncompliant": "Non-Compliant",
    }
    synced = 0
    for d in intune_devices:
        intune_id = d.get("id")
        if not intune_id:
            continue
        existing = db.query(DeviceModel).filter(DeviceModel.intune_id == intune_id).first()
        os_name = f"{d.get('operatingSystem', 'Unknown')} {d.get('osVersion', '')}".strip()
        values = dict(
            hostname=d.get("deviceName", "(unknown)"),
            serial_number=d.get("serialNumber") or None,
            assigned_user=d.get("userPrincipalName") or None,
            os=os_name,
            device_type=d.get("model") or "Unknown",
            compliance_status=compliance_map.get(str(d.get("complianceState", "")).lower(), "Not Evaluated"),
            encryption_status="Encrypted" if d.get("isEncrypted") else "Not Encrypted",
            last_checkin=str(d.get("lastSyncDateTime", "Unknown")),
            management_status="Intune (Live)",
            intune_id=intune_id,
        )
        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            db.add(DeviceModel(**values))
        synced += 1
    db.commit()
    _write_audit(db, "INTUNE_SYNC", f"{synced} device(s)", "SUCCESS")
    return IntuneSyncResult(success=True, synced_count=synced,
                            message=f"Synced {synced} device(s) from Intune.")


def get_identity_overview(db: Session) -> IdentityOverview:
    """
    The operational IAM view: tenant users (live from Entra), which of them
    this tool itself provisioned or offboarded, and who holds privileged
    directory roles. Observations follow the same plain-language pattern as
    the IdentityGovernancePortal, scoped to what an operations tool should
    surface - deeper governance (drift, scoring) lives in that project.
    """
    if not graph_client.is_configured():
        return IdentityOverview(users=[], privileged_roles=[], roles_available=False,
                                observations=["Microsoft Graph not configured yet."])

    managed_upns = {e.upn for e in db.query(EmployeeModel).all() if e.upn}

    users = []
    try:
        raw_users = graph_client.get_users()
    except Exception as exc:
        return IdentityOverview(users=[], privileged_roles=[], roles_available=False,
                                observations=[f"Failed to read users from Entra ID: {exc}"])
    for u in raw_users:
        users.append(IdentityUser(
            display_name=u.get("displayName", ""),
            upn=u.get("userPrincipalName", ""),
            enabled=bool(u.get("accountEnabled", False)),
            licensed=len(u.get("assignedLicenses", [])) > 0,
            department=u.get("department"),
            managed_by_tool=u.get("userPrincipalName", "") in managed_upns,
        ))

    roles_available = True
    privileged_roles = []
    try:
        for r in graph_client.get_directory_roles():
            if r["members"]:  # only roles that actually have holders
                privileged_roles.append(PrivilegedRole(
                    role_name=r["roleName"],
                    members=[m["userPrincipalName"] or m["displayName"] for m in r["members"]],
                ))
    except Exception:
        # Most likely RoleManagement.Read.Directory not granted - degrade honestly.
        roles_available = False

    observations = []
    disabled_licensed = [u for u in users if not u.enabled and u.licensed]
    if disabled_licensed:
        names = ", ".join(u.upn for u in disabled_licensed)
        observations.append(
            f"{len(disabled_licensed)} disabled account(s) still holding a license ({names}). "
            f"Offboarding reclaims licenses; these were likely disabled outside the tool."
        )
    ga = next((r for r in privileged_roles if r.role_name == "Global Administrator"), None)
    if ga:
        if len(ga.members) > 2:
            observations.append(
                f"{len(ga.members)} Global Administrator accounts - above the recommended maximum of 2. "
                f"Review whether each needs standing global rights."
            )
        else:
            observations.append(
                f"{len(ga.members)} Global Administrator account(s) - within the recommended limit."
            )
    if not roles_available:
        observations.append(
            "Privileged role data unavailable - grant RoleManagement.Read.Directory to the app "
            "registration to enable this view."
        )
    tool_managed = [u for u in users if u.managed_by_tool]
    if tool_managed:
        observations.append(
            f"{len(tool_managed)} account(s) in this tenant were provisioned or offboarded by DeviceIdentityOps."
        )

    return IdentityOverview(users=users, privileged_roles=privileged_roles,
                            roles_available=roles_available, observations=observations)
