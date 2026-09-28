import base64
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken


MAL_AUTHORIZE_URL = "https://myanimelist.net/v1/oauth2/authorize"
MAL_TOKEN_URL = "https://myanimelist.net/v1/oauth2/token"
MAL_API_BASE_URL = "https://api.myanimelist.net/v2"
MAL_USER_AGENT = "Sana-Chan MyAnimeList Connection/4.4"


def mal_client_id():
    return (os.getenv("SANA_MAL_CLIENT_ID") or os.getenv("SDAC_MAL_CLIENT_ID") or "").strip()


def mal_client_secret():
    return (os.getenv("SANA_MAL_CLIENT_SECRET") or os.getenv("SDAC_MAL_CLIENT_SECRET") or "").strip()


def mal_configured():
    return bool(mal_client_id() and mal_client_secret())


def mal_redirect_uri(public_url):
    configured = (os.getenv("SANA_MAL_REDIRECT_URI") or os.getenv("SDAC_MAL_REDIRECT_URI") or "").strip()
    if configured:
        return configured
    return f"{str(public_url or '').strip().rstrip('/')}/account/mal/callback"


def new_pkce_verifier():
    return secrets.token_urlsafe(64)[:128]


def mal_authorization_url(redirect_uri, state, code_verifier):
    return MAL_AUTHORIZE_URL + "?" + urlencode({
        "response_type": "code",
        "client_id": mal_client_id(),
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_verifier,
        "code_challenge_method": "plain",
    })


def _mal_error(error, fallback):
    try:
        body = error.read().decode("utf-8")
        payload = json.loads(body)
        detail = payload.get("message") or payload.get("error") or body
    except Exception:
        detail = getattr(error, "reason", "") or str(error)
    return ValueError(f"{fallback}: {str(detail)[:240]}")


def _post_token(payload):
    request = Request(
        MAL_TOKEN_URL,
        data=urlencode(payload).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": MAL_USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise _mal_error(error, "MyAnimeList rejected the account connection") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ValueError("MyAnimeList could not complete the account connection. Try again shortly.") from error
    if not result.get("access_token"):
        raise ValueError("MyAnimeList did not return an access token.")
    return result


def exchange_mal_code(code, redirect_uri, code_verifier):
    return _post_token({
        "client_id": mal_client_id(),
        "client_secret": mal_client_secret(),
        "grant_type": "authorization_code",
        "code": str(code or ""),
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    })


def refresh_mal_token(refresh_token):
    return _post_token({
        "client_id": mal_client_id(),
        "client_secret": mal_client_secret(),
        "grant_type": "refresh_token",
        "refresh_token": str(refresh_token or ""),
    })


def mal_token_expiry(token_payload):
    try:
        seconds = max(60, int(token_payload.get("expires_in") or 3600))
    except (TypeError, ValueError):
        seconds = 3600
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def mal_token_needs_refresh(expires_at, leeway_seconds=120):
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
        raise ValueError("SDAC_SECRET_KEY is required before MyAnimeList accounts can be connected.")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt_mal_token(token, secret_key):
    if not token:
        return ""
    return _fernet(secret_key).encrypt(str(token).encode("utf-8")).decode("ascii")


def decrypt_mal_token(token, secret_key):
    if not token:
        return ""
    try:
        return _fernet(secret_key).decrypt(str(token).encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError) as error:
        raise ValueError("The saved MyAnimeList connection could not be decrypted. Reconnect the account.") from error


def mal_api_json(access_token, path_or_url, parameters=None):
    if str(path_or_url).startswith("https://"):
        url = str(path_or_url)
        if not url.startswith(MAL_API_BASE_URL + "/"):
            raise ValueError("MyAnimeList returned an unsafe paging URL.")
    else:
        url = MAL_API_BASE_URL + "/" + str(path_or_url).lstrip("/")
    if parameters:
        url += ("&" if "?" in url else "?") + urlencode(parameters)
    request = Request(url, headers={
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "User-Agent": MAL_USER_AGENT,
    })
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 401:
            raise ValueError("The MyAnimeList connection expired. Reconnect the account.") from error
        raise _mal_error(error, "MyAnimeList API request failed") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ValueError("MyAnimeList could not be reached. Try syncing again shortly.") from error


def mal_current_user(access_token):
    payload = mal_api_json(access_token, "/users/@me")
    if not payload.get("id") or not payload.get("name"):
        raise ValueError("MyAnimeList did not return the connected account identity.")
    return payload


def _mal_user_list(access_token, kind):
    endpoint = f"/users/@me/{'animelist' if kind == 'anime' else 'mangalist'}"
    payload = mal_api_json(access_token, endpoint, {
        "fields": "list_status",
        "limit": 1000,
        "sort": "list_updated_at",
    })
    rows = list(payload.get("data") or [])
    next_url = (payload.get("paging") or {}).get("next")
    pages = 1
    while next_url and pages < 5:
        payload = mal_api_json(access_token, next_url)
        rows.extend(payload.get("data") or [])
        next_url = (payload.get("paging") or {}).get("next")
        pages += 1
    return rows


def _clean_title(value):
    return " ".join(str(value or "").split())[:160]


def _entry_title(entry):
    return _clean_title((entry.get("node") or {}).get("title"))


def _entry_status(entry):
    return str((entry.get("list_status") or {}).get("status") or "").casefold()


def _entry_score(entry):
    try:
        return int((entry.get("list_status") or {}).get("score") or 0)
    except (TypeError, ValueError):
        return 0


def _entry_image(entry):
    pictures = (entry.get("node") or {}).get("main_picture") or {}
    value = str(pictures.get("medium") or pictures.get("large") or "").strip()
    return value if value.startswith("https://") else ""


def _unique_values(values, limit):
    output = []
    seen = set()
    for value in values:
        cleaned = str(value or "").strip()
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
        if len(output) >= limit:
            break
    return output


def _completed_highlights(entries):
    completed = [entry for entry in entries if _entry_status(entry) == "completed" and _entry_title(entry)]
    completed.sort(key=lambda entry: (_entry_score(entry), str((entry.get("list_status") or {}).get("updated_at") or "")), reverse=True)
    return completed


def mal_profile_summary(access_token, user=None):
    user = user or mal_current_user(access_token)
    anime = _mal_user_list(access_token, "anime")
    manga = _mal_user_list(access_token, "manga")
    active_anime = [entry for entry in anime if _entry_status(entry) in {"watching", "on_hold", "plan_to_watch"}]
    active_manga = [entry for entry in manga if _entry_status(entry) in {"reading", "on_hold", "plan_to_read"}]
    completed_anime = _completed_highlights(anime)
    completed_manga = _completed_highlights(manga)
    anime_favorites = _unique_values((_entry_title(entry) for entry in completed_anime or active_anime), 8)
    manga_favorites = _unique_values((_entry_title(entry) for entry in completed_manga or active_manga), 8)
    anime_active_titles = _unique_values((_entry_title(entry) for entry in active_anime), 8)
    manga_active_titles = _unique_values((_entry_title(entry) for entry in active_manga), 8)
    anime_images = _unique_values((_entry_image(entry) for entry in active_anime + completed_anime), 3)
    manga_images = _unique_values((_entry_image(entry) for entry in active_manga + completed_manga), 3)
    username = _clean_title(user.get("name"))
    return {
        "username": username,
        "mal_user_id": str(user.get("id") or ""),
        "mal_profile_url": f"https://myanimelist.net/profile/{quote(username, safe='')}",
        "anime_favorites": ", ".join(anime_favorites) or "No completed anime highlights found.",
        "anime_watching": ("Watching: " + ", ".join(anime_active_titles)) if anime_active_titles else "No active anime entries found.",
        "manga_favorites": ", ".join(manga_favorites) or "No completed manga highlights found.",
        "manga_reading": ("Reading: " + ", ".join(manga_active_titles)) if manga_active_titles else "No active manga entries found.",
        "anime_preview_images": anime_images,
        "manga_preview_images": manga_images,
        "anime_count": len(anime),
        "manga_count": len(manga),
    }
