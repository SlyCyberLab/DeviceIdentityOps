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
from app.models import Device as DeviceModel, Employee as EmployeeModel, AuditLog as AuditLogModel
from app.schemas import (
    DeviceOut,
    DeviceDeployRequest,
    DeviceDeployResult,
    ProcessRequestsResult,
    AuditLogOut,
    OnboardingRequestSubmit,
    OffboardingRequestSubmit,
    SubmitResult,
)

# Safety default: real device/identity actions stay simulated until this is
# explicitly flipped in a controlled environment (see .env.example).
DRY_RUN = True

# Department -> Intune policy group. Deliberately simple - a real system
# would look this up from a policy table, but the rule itself isn't the
# point of the demo.
_POLICY_MAP = {
    "Engineering": "ENG-Standard-Policy",
    "Sales": "SALES-Standard-Policy",
    "Operations": "OPS-Standard-Policy",
    "HR": "HR-Standard-Policy",
    "Finance": "FIN-Standard-Policy",
}


def _write_audit(db: Session, action_type: str, target: str, result: str) -> None:
    entry = AuditLogModel(
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        action_type=action_type,
        target=target,
        result=result,
    )
    db.add(entry)
    db.commit()


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


def deploy_device(db: Session, request: DeviceDeployRequest) -> DeviceDeployResult:
    """
    Validate -> assign -> determine policy -> record.

    "Deployed" here means a new row in the devices table with a status that
    reflects it hasn't actually enrolled/checked in yet - this workflow
    stays simulated by design (see README for why).
    """
    # Validate: reject a serial number that's already been deployed.
    existing = db.query(DeviceModel).filter(DeviceModel.serial_number == request.serial_number).first()
    if existing:
        _write_audit(db, "DEVICE_DEPLOYMENT", request.serial_number, "FAILED")
        return DeviceDeployResult(
            success=False,
            message=f"Serial {request.serial_number} is already deployed - refusing to create a duplicate.",
            policy_assigned=None,
            dry_run=DRY_RUN,
        )

    policy = _POLICY_MAP.get(request.department, "Default-Policy")

    new_device = DeviceModel(
        hostname=request.hostname,
        serial_number=request.serial_number,
        assigned_user=request.assigned_user,
        os="Unknown (Pending Enrollment)",
        device_type=request.device_type,
        compliance_status="Pending Enrollment",
        encryption_status="Pending Enrollment",
        last_checkin="Not yet checked in",
        management_status="Deployed (Dry-Run)" if DRY_RUN else "Deployed",
    )
    db.add(new_device)
    db.commit()

    _write_audit(db, "DEVICE_DEPLOYMENT", request.hostname, "SUCCESS")

    return DeviceDeployResult(
        success=True,
        message=f"Device {request.hostname} (serial {request.serial_number}) assigned to {request.assigned_user}",
        policy_assigned=policy,
        dry_run=DRY_RUN,
    )


def remove_device(db: Session, device_id: int) -> DeviceDeployResult:
    """Removes a device record and logs the removal. Only affects DeviceIdentityOps's
    own record - does not touch Intune enrollment (that's a separate, real action
    that would need graph_client in Phase 8)."""
    device = db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
    if not device:
        return DeviceDeployResult(success=False, message="Device not found.", policy_assigned=None, dry_run=DRY_RUN)

    hostname = device.hostname
    db.delete(device)
    db.commit()
    _write_audit(db, "DEVICE_REMOVED", hostname, "SUCCESS")
    return DeviceDeployResult(success=True, message=f"Device {hostname} removed.", policy_assigned=None, dry_run=DRY_RUN)


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
