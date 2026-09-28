import base64
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken


ANILIST_AUTHORIZE_URL = "https://anilist.co/api/v2/oauth/authorize"
ANILIST_TOKEN_URL = "https://anilist.co/api/v2/oauth/token"
ANILIST_GRAPHQL_URL = "https://graphql.anilist.co"
ANILIST_USER_AGENT = "Sana-Chan AniList Connection/4.4"


def anilist_client_id():
    return (os.getenv("SANA_ANILIST_CLIENT_ID") or os.getenv("SDAC_ANILIST_CLIENT_ID") or "").strip()


def anilist_client_secret():
    return (os.getenv("SANA_ANILIST_CLIENT_SECRET") or os.getenv("SDAC_ANILIST_CLIENT_SECRET") or "").strip()


def anilist_configured():
    return bool(anilist_client_id() and anilist_client_secret())


def anilist_redirect_uri(public_url):
    configured = (os.getenv("SANA_ANILIST_REDIRECT_URI") or os.getenv("SDAC_ANILIST_REDIRECT_URI") or "").strip()
    if configured:
        return configured
    return f"{str(public_url or '').strip().rstrip('/')}/account/anilist/callback"


def anilist_authorization_url(redirect_uri, state):
    return ANILIST_AUTHORIZE_URL + "?" + urlencode({
        "client_id": anilist_client_id(),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
    })


def _service_error(error, fallback):
    try:
        payload = json.loads(error.read().decode("utf-8"))
        detail = payload.get("message") or payload.get("error_description") or payload.get("error") or str(payload)
    except Exception:
        detail = getattr(error, "reason", "") or str(error)
    return ValueError(f"{fallback}: {str(detail)[:240]}")


def exchange_anilist_code(code, redirect_uri):
    request = Request(
        ANILIST_TOKEN_URL,
        data=json.dumps({
            "grant_type": "authorization_code",
            "client_id": anilist_client_id(),
            "client_secret": anilist_client_secret(),
            "redirect_uri": redirect_uri,
            "code": str(code or ""),
        }).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": ANILIST_USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise _service_error(error, "AniList rejected the account connection") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ValueError("AniList could not complete the account connection. Try again shortly.") from error
    if not payload.get("access_token"):
        raise ValueError("AniList did not return an access token.")
    return payload


def anilist_token_expiry(token_payload):
    try:
        seconds = max(60, int(token_payload.get("expires_in") or 31536000))
    except (TypeError, ValueError):
        seconds = 31536000
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def anilist_token_expired(expires_at, leeway_seconds=120):
    try:
        parsed = datetime.fromisoformat(str(expires_at or "").replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return True
    return parsed <= datetime.now(timezone.utc) + timedelta(seconds=leeway_seconds)


def _fernet(secret_key):
    secret = str(secret_key or "").encode("utf-8")
    if not secret:
        raise ValueError("SDAC_SECRET_KEY is required before AniList accounts can be connected.")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret).digest()))


def encrypt_anilist_token(token, secret_key):
    if not token:
        return ""
    return _fernet(secret_key).encrypt(str(token).encode("utf-8")).decode("ascii")


def decrypt_anilist_token(token, secret_key):
    if not token:
        return ""
    try:
        return _fernet(secret_key).decrypt(str(token).encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError) as error:
        raise ValueError("The saved AniList connection could not be decrypted. Reconnect the account.") from error


def anilist_graphql(access_token, query, variables=None):
    request = Request(
        ANILIST_GRAPHQL_URL,
        data=json.dumps({"query": query, "variables": variables or {}}).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": ANILIST_USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code in {401, 403}:
            raise ValueError("The AniList connection expired. Reconnect the account.") from error
        raise _service_error(error, "AniList API request failed") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ValueError("AniList could not be reached. Try syncing again shortly.") from error
    if payload.get("errors"):
        detail = "; ".join(str(item.get("message") or "Unknown error") for item in payload["errors"][:3])
        raise ValueError(f"AniList API request failed: {detail[:300]}")
    return payload.get("data") or {}


def anilist_current_user(access_token):
    data = anilist_graphql(access_token, """
        query {
          Viewer { id name avatar { large medium } siteUrl }
        }
    """)
    user = data.get("Viewer") or {}
    if not user.get("id") or not user.get("name"):
        raise ValueError("AniList did not return the connected account identity.")
    return user


ANILIST_LIST_QUERY = """
query ($type: MediaType!, $userId: Int!) {
  MediaListCollection(type: $type, userId: $userId) {
    lists {
      name
      isCustomList
      entries {
        id status score progress progressVolumes repeat notes private updatedAt startedAt { year month day } completedAt { year month day }
        media {
          id idMal type format status episodes chapters volumes siteUrl
          title { romaji english native userPreferred }
          coverImage { extraLarge large medium }
        }
      }
    }
  }
}
"""


def _anilist_list(access_token, user_id, media_type):
    data = anilist_graphql(
        access_token,
        ANILIST_LIST_QUERY,
        {"type": str(media_type).upper(), "userId": int(user_id)},
    )
    lists = ((data.get("MediaListCollection") or {}).get("lists") or [])
    entries = []
    seen = set()
    for list_group in lists:
        for entry in list_group.get("entries") or []:
            entry_id = str(entry.get("id") or "")
            if not entry_id or entry_id in seen:
                continue
            seen.add(entry_id)
            copied = dict(entry)
            copied["list_name"] = str(list_group.get("name") or "")
            entries.append(copied)
    return entries


def _clean(value, limit=160):
    return " ".join(str(value or "").split())[:limit]


def _title(entry):
    titles = ((entry.get("media") or {}).get("title") or {})
    return _clean(titles.get("userPreferred") or titles.get("english") or titles.get("romaji") or titles.get("native"))


def _image(entry):
    images = ((entry.get("media") or {}).get("coverImage") or {})
    value = str(images.get("large") or images.get("extraLarge") or images.get("medium") or "").strip()
    return value if value.startswith("https://") else ""


def _score(entry):
    try:
        return float(entry.get("score") or 0)
    except (TypeError, ValueError):
        return 0.0


def _unique(values, limit):
    output = []
    seen = set()
    for value in values:
        value = str(value or "").strip()
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        output.append(value)
        if len(output) >= limit:
            break
    return output


def anilist_account_data(access_token, user=None):
    user = user or anilist_current_user(access_token)
    return {
        "user": user,
        "anime": _anilist_list(access_token, user["id"], "ANIME"),
        "manga": _anilist_list(access_token, user["id"], "MANGA"),
    }


def anilist_profile_summary(access_token, user=None, account_data=None):
    data = account_data or anilist_account_data(access_token, user)
    user = data["user"]
    anime = data["anime"]
    manga = data["manga"]
    active_anime = [entry for entry in anime if str(entry.get("status") or "").upper() in {"CURRENT", "PAUSED", "PLANNING"}]
    active_manga = [entry for entry in manga if str(entry.get("status") or "").upper() in {"CURRENT", "PAUSED", "PLANNING"}]
    complete_anime = sorted((entry for entry in anime if str(entry.get("status") or "").upper() == "COMPLETED"), key=_score, reverse=True)
    complete_manga = sorted((entry for entry in manga if str(entry.get("status") or "").upper() == "COMPLETED"), key=_score, reverse=True)
    username = _clean(user.get("name"), 120)
    return {
        "username": username,
        "anilist_user_id": str(user.get("id") or ""),
        "anilist_profile_url": str(user.get("siteUrl") or f"https://anilist.co/user/{quote(username, safe='')}/"),
        "anime_favorites": ", ".join(_unique((_title(entry) for entry in complete_anime or active_anime), 8)) or "No completed anime highlights found.",
        "anime_watching": ("Watching: " + ", ".join(_unique((_title(entry) for entry in active_anime), 8))) if active_anime else "No active anime entries found.",
        "manga_favorites": ", ".join(_unique((_title(entry) for entry in complete_manga or active_manga), 8)) or "No completed manga highlights found.",
        "manga_reading": ("Reading: " + ", ".join(_unique((_title(entry) for entry in active_manga), 8))) if active_manga else "No active manga entries found.",
        "anime_preview_images": _unique((_image(entry) for entry in active_anime + complete_anime), 3),
        "manga_preview_images": _unique((_image(entry) for entry in active_manga + complete_manga), 3),
        "anime_count": len(anime),
        "manga_count": len(manga),
    }


def anilist_export_payload(access_token, user=None):
    data = anilist_account_data(access_token, user)
    return {
        "schema": "sana-chan-anilist-export-v1",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": "AniList authenticated account",
        "user": data["user"],
        "anime": data["anime"],
        "manga": data["manga"],
    }
