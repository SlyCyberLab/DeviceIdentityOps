"""
Microsoft Graph client - isolated in one place so all auth and Graph calls
live here. Swapping mock -> real, or changing permissions, only ever
touches this file.

Uses app-only auth (client credentials flow via MSAL) against the
DeviceIdentityOps tenant - the same pattern used in the Identity Lifecycle
Automation project, just Python instead of PowerShell.

TODO (Phase 8):
- get_access_token()
- get_managed_devices()          # real Intune-enrolled device(s)
- create_user() / disable_user()
- set_usage_location() / assign_license() / remove_license()
- add_to_group() / remove_from_group()   # SharePoint access provisioning
- invalidate_sessions()
- send_mail()
"""
