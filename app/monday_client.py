"""
Monday.com outbound integration - feature-flagged.

DeviceIdentityOps pushes its audit events (onboarding, offboarding, device
sync) to a Monday.com board so the engineering/project teams who already
live in Monday can see IT automation activity without needing Intune or
Entra access. This is outbound-only by design: one authenticated GraphQL
mutation per event, no public endpoint, no webhook handshake.

Entirely optional. If MONDAY_API_TOKEN isn't set, every call here is a
silent no-op - the rest of the app runs identically with or without it.
The talking point: "IT actions surface on the board the project teams
already watch; swapping to an inbound webhook later wouldn't change the
audit pipeline, since this just mirrors what already gets logged."
"""

import os
import json
import requests

MONDAY_API = "https://api.monday.com/v2"


def is_enabled() -> bool:
    return bool(os.getenv("MONDAY_API_TOKEN") and os.getenv("MONDAY_BOARD_ID"))


def post_event(action_type: str, target: str, result: str) -> None:
    """
    Mirror one audit event to the Monday board as a new item. Best-effort:
    any failure is swallowed so a Monday problem never breaks an IT action
    that already succeeded. No-op when the integration isn't configured.
    """
    if not is_enabled():
        return
    token = os.getenv("MONDAY_API_TOKEN")
    board_id = os.getenv("MONDAY_BOARD_ID")

    item_name = f"{action_type}: {target}"
    # column values keyed by the board's column IDs; kept minimal and
    # tolerant - a board without these columns still creates the item.
    column_values = json.dumps({
        "status": {"label": result},
        "text": target,
    })

    mutation = """
    mutation ($board: ID!, $name: String!, $cols: JSON!) {
      create_item (board_id: $board, item_name: $name, column_values: $cols) { id }
    }
    """
    try:
        requests.post(
            MONDAY_API,
            json={"query": mutation, "variables": {
                "board": board_id, "name": item_name, "cols": column_values,
            }},
            headers={"Authorization": token, "Content-Type": "application/json"},
            timeout=5,
        )
    except Exception:
        # Outbound telemetry must never break the primary workflow.
        pass
