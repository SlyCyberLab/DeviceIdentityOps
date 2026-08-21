"""
Microsoft Graph client - isolated in one place so all auth and Graph calls
live here. Swapping mock -> real, or changing permissions, only ever
touches this file - main.py and logic.py never need to change when this
gets wired up.

Uses app-only auth (client credentials flow via MSAL), the same pattern
used in the Identity Lifecycle Automation project, just Python instead of
PowerShell, and against a cloud-only tenant instead of hybrid.

Phase 6: function signatures and the "not configured" seam are in place.
Phase 8: fills in the real MSAL token acquisition and Graph calls once the
Business Premium tenant + app registration exist.
"""

import os


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
    """TODO (Phase 8): MSAL ConfidentialClientApplication, client credentials flow."""
    _require_configured()
    raise NotImplementedError("Phase 8")


# ---------- Devices (Intune) ----------

def get_managed_devices() -> list[dict]:
    """TODO (Phase 8): GET /deviceManagement/managedDevices - the one real enrolled VM."""
    _require_configured()
    raise NotImplementedError("Phase 8")


# ---------- SharePoint request lists ----------

def get_pending_onboarding_requests() -> list[dict]:
    """TODO (Phase 8): GET /sites/{site-id}/lists/{list-id}/items, filter Status=Pending."""
    _require_configured()
    raise NotImplementedError("Phase 8")


def get_pending_offboarding_requests() -> list[dict]:
    """TODO (Phase 8): same pattern, offboarding list."""
    _require_configured()
    raise NotImplementedError("Phase 8")


def write_back_status(list_id: str, item_id: str, status: str, upn: str = None) -> None:
    """TODO (Phase 8): PATCH the SharePoint list item's Status field to Completed/Failed."""
    _require_configured()
    raise NotImplementedError("Phase 8")


# ---------- Entra ID identity actions ----------

def create_user(display_name: str, department: str) -> dict:
    """TODO (Phase 8): POST /users - cloud-only Entra ID user, no AD/sync involved."""
    _require_configured()
    raise NotImplementedError("Phase 8")


def set_usage_location(user_id: str, location: str = "US") -> None:
    """TODO (Phase 8): required before license assignment."""
    _require_configured()
    raise NotImplementedError("Phase 8")


def assign_license(user_id: str, sku_id: str) -> None:
    """TODO (Phase 8): POST /users/{id}/assignLicense."""
    _require_configured()
    raise NotImplementedError("Phase 8")


def remove_license(user_id: str, sku_id: str) -> None:
    """TODO (Phase 8): offboarding mirror of assign_license."""
    _require_configured()
    raise NotImplementedError("Phase 8")


def disable_user(user_id: str) -> None:
    """TODO (Phase 8): PATCH /users/{id} accountEnabled: false."""
    _require_configured()
    raise NotImplementedError("Phase 8")


def invalidate_sessions(user_id: str) -> None:
    """TODO (Phase 8): POST /users/{id}/invalidateAllRefreshTokens."""
    _require_configured()
    raise NotImplementedError("Phase 8")


def add_to_group(user_id: str, group_id: str) -> None:
    """TODO (Phase 8): SharePoint access provisioning via Entra ID group membership."""
    _require_configured()
    raise NotImplementedError("Phase 8")


def remove_from_group(user_id: str, group_id: str) -> None:
    """TODO (Phase 8): offboarding mirror of add_to_group."""
    _require_configured()
    raise NotImplementedError("Phase 8")


def send_mail(to_address: str, subject: str, body: str) -> None:
    """TODO (Phase 8): POST /users/{sender-id}/sendMail."""
    _require_configured()
    raise NotImplementedError("Phase 8")
