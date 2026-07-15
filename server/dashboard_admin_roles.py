"""Shared dashboard role constants and pure role helpers."""

ROLE_LEVELS = {
    "not_added": -1,
    "user": 0,
    "trusted": 0,
    "moderator": 1,
    "admin": 2,
    "owner": 3,
    "bot_owner": 4,
}

ROLE_LABELS = {
    "not_added": "Not Added",
    "user": "User",
    "trusted": "Trusted User",
    "moderator": "Moderator",
    "admin": "Admin",
    "owner": "Server Owner",
    "bot_owner": "Bot Owner",
}

OWNER_OVERRIDE_USERNAME = "baytae"


def normalize_role(role):
    key = str(role or "").strip().casefold().replace("-", "_")
    if key in {"notadded", "not added", "not_added", "none", "unverified"}:
        key = "not_added"
    if key in {"server_owner", "server owner"}:
        key = "owner"
    if key in {"botowner", "bot owner", "global_owner", "global owner"}:
        key = "bot_owner"
    return key if key in ROLE_LEVELS else "user"


def role_at_least(role, required_role):
    return ROLE_LEVELS[normalize_role(role)] >= ROLE_LEVELS[normalize_role(required_role)]
