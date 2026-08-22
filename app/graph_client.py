"""
Microsoft Graph client - isolated in one place so all auth and Graph calls
live here. Swapping mock -> real, or changing permissions, only ever
touches this file - main.py and logic.py never need to change when this
gets wired up.

Uses app-only auth (client credentials flow via MSAL), the same pattern
used in the Identity Lifecycle Automation project, just Python instead of
PowerShell, and against a cloud-only tenant instead of hybrid.

Phase 8: real MSAL token acquisition and Graph calls, against the
sleytech.com Business Premium trial tenant.
"""

import os
import msal
import requests

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Business Premium (SPB) SKU on this tenant. Note: the internal Graph SKU
# string "O365_BUSINESS_PREMIUM" is a legacy Microsoft naming quirk and
# actually maps to today's "Business Standard" product - SPB is the real
# Business Premium SKU (Intune, Defender for Business, Entra ID P1).
BUSINESS_PREMIUM_SKU_ID = "cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46"

_token_cache = {"token": None}


class GraphNotConfiguredError(Exception):
    """Raised when TENANT_ID/CLIENT_ID/CLIENT_SECRET aren't set yet."""
    pass


def is_configured() -> bool:
    return bool(os.getenv("TENANT_ID") and os.getenv("CLIENT_ID") and os.getenv("CLIENT_SECRET"))


def _require_configured() -> None:
    if not is_configured():
        raise GraphNotConfiguredError(
            "Microsoft Graph isn't configured yet. Set TENANT_ID, CLIENT_ID, "
            "and CLIENT_SECRET in .env once the app registration exists (Phase 8)."
        )


def get_access_token() -> str:
    """
    MSAL client credentials flow (app-only auth). MSAL handles caching and
    expiry internally when reusing the same app instance, so we build one
    ConfidentialClientApplication and let it manage token refresh.
    """
    _require_configured()
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")

    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(f"Graph auth failed: {result.get('error_description', result)}")
    return result["access_token"]


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
    }


def _get(path: str, params: dict = None, extra_headers: dict = None) -> dict:
    headers = _headers()
    if extra_headers:
        headers.update(extra_headers)
    resp = requests.get(f"{GRAPH_BASE}{path}", headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, body: dict) -> dict:
    resp = requests.post(f"{GRAPH_BASE}{path}", headers=_headers(), json=body)
    resp.raise_for_status()
    return resp.json() if resp.text else {}


def _patch(path: str, body: dict) -> None:
    resp = requests.patch(f"{GRAPH_BASE}{path}", headers=_headers(), json=body)
    resp.raise_for_status()


def _delete(path: str) -> None:
    resp = requests.delete(f"{GRAPH_BASE}{path}", headers=_headers())
    resp.raise_for_status()


# ---------- Devices (Intune) ----------

def get_managed_devices() -> list[dict]:
    """GET /deviceManagement/managedDevices - the real Intune-enrolled device(s)."""
    data = _get("/deviceManagement/managedDevices")
    return data.get("value", [])


# ---------- SharePoint request lists ----------

def _get_pending_requests(list_id: str) -> list[dict]:
    site_id = os.getenv("SHAREPOINT_SITE_ID")
    # Status isn't an indexed SharePoint column, so Graph requires this header
    # to allow filtering on it - without it, the query returns a 400.
    data = _get(
        f"/sites/{site_id}/lists/{list_id}/items",
        params={"expand": "fields", "$filter": "fields/Status eq 'Pending'"},
        extra_headers={"Prefer": "HonorNonIndexedQueriesWarningMayFailRandomly"},
    )
    items = []
    for item in data.get("value", []):
        fields = item.get("fields", {})
        fields["item_id"] = item["id"]
        fields["list_id"] = list_id
        items.append(fields)
    return items


def get_pending_onboarding_requests() -> list[dict]:
    """Reads Pending items from the New Hire Requests SharePoint list."""
    list_id = os.getenv("ONBOARDING_LIST_ID")
    raw = _get_pending_requests(list_id)
    requests_out = []
    for r in raw:
        requests_out.append({
            "display_name": f"{r.get('FirstName', '')} {r.get('LastName', '')}".strip(),
            "department": r.get("Department", ""),
            "start_date": str(r.get("StartDate", ""))[:10],
            "manager_email": r.get("ManagerEmail", ""),
            "license_sku": BUSINESS_PREMIUM_SKU_ID,
            "access_group": None,  # set once an access group exists; optional for now
            "item_id": r["item_id"],
            "list_id": r["list_id"],
        })
    return requests_out


def get_pending_offboarding_requests() -> list[dict]:
    """Reads Pending items from the Offboarding Requests SharePoint list."""
    list_id = os.getenv("OFFBOARDING_LIST_ID")
    raw = _get_pending_requests(list_id)
    requests_out = []
    for r in raw:
        requests_out.append({
            "display_name": r.get("DisplayName", "") or r.get("Title", ""),
            "upn": r.get("UPN", ""),
            "user_id": r.get("UPN", ""),  # Graph's /users/{id} accepts UPN as an alternate key
            "last_working_day": str(r.get("LastWorkingDay", ""))[:10],
            "manager_email": r.get("ManagerEmail", ""),
            "license_sku": BUSINESS_PREMIUM_SKU_ID,
            "access_group": None,
            "item_id": r["item_id"],
            "list_id": r["list_id"],
        })
    return requests_out


def write_back_status(list_id: str, item_id: str, status: str, upn: str = None) -> None:
    """PATCH the SharePoint list item's Status field (and UPN, for onboarding)."""
    fields = {"Status": status}
    if upn:
        fields["UPN"] = upn
    site_id = os.getenv("SHAREPOINT_SITE_ID")
    _patch(f"/sites/{site_id}/lists/{list_id}/items/{item_id}/fields", fields)


# ---------- Entra ID identity actions ----------

def create_user(display_name: str, department: str) -> dict:
    """POST /users - cloud-only Entra ID user, no AD/sync involved."""
    domain = os.getenv("PRIMARY_DOMAIN", "sleytech.com")
    local_part = display_name.lower().replace(" ", ".")
    upn = f"{local_part}@{domain}"
    import secrets
    temp_password = secrets.token_urlsafe(12)

    body = {
        "accountEnabled": True,
        "displayName": display_name,
        "department": department,
        "mailNickname": local_part.replace(".", ""),
        "userPrincipalName": upn,
        "passwordProfile": {
            "forceChangePasswordNextSignIn": True,
            "password": temp_password,
        },
    }
    user = _post("/users", body)
    user["_temp_password"] = temp_password  # only used locally to build the notification email
    return user


def set_usage_location(user_id: str, location: str = "US") -> None:
    """Required before license assignment."""
    _patch(f"/users/{user_id}", {"usageLocation": location})


def assign_license(user_id: str, sku_id: str = None) -> None:
    """POST /users/{id}/assignLicense."""
    sku_id = sku_id or BUSINESS_PREMIUM_SKU_ID
    _post(f"/users/{user_id}/assignLicense", {
        "addLicenses": [{"skuId": sku_id}],
        "removeLicenses": [],
    })


def remove_license(user_id: str, sku_id: str = None) -> None:
    """Offboarding mirror of assign_license."""
    sku_id = sku_id or BUSINESS_PREMIUM_SKU_ID
    _post(f"/users/{user_id}/assignLicense", {
        "addLicenses": [],
        "removeLicenses": [sku_id],
    })


def disable_user(user_id: str) -> None:
    """PATCH /users/{id} accountEnabled: false."""
    _patch(f"/users/{user_id}", {"accountEnabled": False})


def invalidate_sessions(user_id: str) -> None:
    """POST /users/{id}/invalidateAllRefreshTokens."""
    _post(f"/users/{user_id}/invalidateAllRefreshTokens", {})


def add_to_group(user_id: str, group_id: str) -> None:
    """SharePoint access provisioning via Entra ID group membership. No-op if no group configured yet."""
    if not group_id:
        return
    _post(f"/groups/{group_id}/members/$ref", {
        "@odata.id": f"{GRAPH_BASE}/directoryObjects/{user_id}"
    })


def remove_from_group(user_id: str, group_id: str) -> None:
    """Offboarding mirror of add_to_group. No-op if no group configured yet."""
    if not group_id:
        return
    _delete(f"/groups/{group_id}/members/{user_id}/$ref")


def send_mail(to_address: str, subject: str, body: str) -> None:
    """POST /users/{sender-id}/sendMail, sent from the admin account."""
    sender = os.getenv("SENDER_UPN", "admin@sleytech.com")
    _post(f"/users/{sender}/sendMail", {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": to_address}}],
        },
        "saveToSentItems": "true",
    })


# ---------- Request submission (the "front door") ----------
# These create new items in the SharePoint lists - the reverse direction
# of get_pending_*_requests(), which reads them. Together they mean
# DeviceIdentityOps is a self-contained front door: submit a request here,
# it's a real SharePoint list item, Process Requests reads it back exactly
# the same way it would read one submitted through a Power Apps form or
# any other tool - SharePoint stays the actual system of record either way.

def create_onboarding_request(fields: dict) -> dict:
    """POST a new Pending item to the New Hire Requests list."""
    site_id = os.getenv("SHAREPOINT_SITE_ID")
    list_id = os.getenv("ONBOARDING_LIST_ID")
    body = {"fields": {**fields, "Status": "Pending"}}
    return _post(f"/sites/{site_id}/lists/{list_id}/items", body)


def create_offboarding_request(fields: dict) -> dict:
    """POST a new Pending item to the Offboarding Requests list."""
    site_id = os.getenv("SHAREPOINT_SITE_ID")
    list_id = os.getenv("OFFBOARDING_LIST_ID")
    body = {"fields": {**fields, "Status": "Pending"}}
    return _post(f"/sites/{site_id}/lists/{list_id}/items", body)


# ---------- Identity & Access (IAM) ----------

def get_users() -> list[dict]:
    """
    GET /users - the tenant's user accounts with enabled state and license
    presence. Feeds the Identity & Access view: the operational half of IAM
    (who exists, who's disabled, who holds a license) - governance-depth
    analysis (drift, scoring) deliberately lives in the separate
    IdentityGovernancePortal project.
    """
    data = _get("/users", params={
        "$select": "id,displayName,userPrincipalName,accountEnabled,assignedLicenses,department",
        "$top": "50",
    })
    return data.get("value", [])


def get_directory_roles() -> list[dict]:
    """
    GET /directoryRoles + members - who holds privileged roles ("who has
    the keys"). Requires RoleManagement.Read.Directory; if that permission
    isn't granted yet this raises, and the caller degrades gracefully with
    an honest "unavailable" note rather than hiding the section.
    """
    roles = _get("/directoryRoles").get("value", [])
    out = []
    for role in roles:
        members_data = _get(f"/directoryRoles/{role['id']}/members")
        members = [
            {
                "displayName": m.get("displayName", ""),
                "userPrincipalName": m.get("userPrincipalName", ""),
            }
            for m in members_data.get("value", [])
        ]
        out.append({
            "roleName": role.get("displayName", ""),
            "members": members,
        })
    return out
