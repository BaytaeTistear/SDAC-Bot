"""Production-facing services shared by the dashboard, bot, and operations jobs."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def create_inbox_notification(connection, user_id, title, body, category="general", action_url=""):
    if not str(user_id or "").strip():
        return None
    cursor = connection.execute(
        """INSERT INTO user_notifications
           (user_id,title,body,category,action_url,is_read,created_at)
           VALUES (?,?,?,?,?,0,?)""",
        (str(user_id), str(title)[:160], str(body)[:2000], str(category)[:40], str(action_url)[:500], utc_now_iso()),
    )
    return int(cursor.lastrowid)


def enqueue_webhook(connection, event_key, guild_id, payload):
    event_id = secrets.token_urlsafe(24)
    now = utc_now_iso()
    connection.execute(
        """INSERT INTO webhook_outbox
           (event_id,event_key,guild_id,payload_json,status,attempt_count,next_attempt_at,created_at,updated_at)
           VALUES (?,?,?,?,'pending',0,?,?,?)""",
        (event_id, str(event_key), str(guild_id or ""), json.dumps(payload, separators=(",", ":")), now, now, now),
    )
    return event_id


def schedule_webhook_retry(connection, outbox_id, attempts, error=""):
    attempts = int(attempts)
    terminal = attempts >= 5
    delay_minutes = min(60, 2 ** max(0, attempts - 1))
    next_attempt = (datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)).isoformat()
    connection.execute(
        """UPDATE webhook_outbox SET status=?,attempt_count=?,next_attempt_at=?,last_error=?,updated_at=? WHERE id=?""",
        ("dead" if terminal else "retry", attempts, next_attempt, str(error)[:1000], utc_now_iso(), int(outbox_id)),
    )


def record_service_metric(connection, metric_key, value, unit="count", guild_id="", details=None):
    connection.execute(
        """INSERT INTO service_metrics (metric_key,metric_value,unit,guild_id,details_json,created_at)
           VALUES (?,?,?,?,?,?)""",
        (str(metric_key)[:100], float(value), str(unit)[:30], str(guild_id or ""), json.dumps(details or {}, separators=(",", ":")), utc_now_iso()),
    )


def openapi_document(base_url=""):
    base_url = str(base_url or "").rstrip("/")
    return {
        "openapi": "3.1.0",
        "info": {"title": "Sana-Chan Public API", "version": "1.0.0", "description": "Read-only approved community content. Requests are rate limited and never expose private moderation data."},
        "servers": [{"url": base_url}] if base_url else [],
        "paths": {
            "/api/v1/quotes": {"get": {"summary": "List approved quotes", "parameters": _list_parameters(), "responses": {"200": {"description": "Approved quote collection"}, "400": {"description": "Invalid limit"}, "404": {"description": "Server is not public"}}}},
            "/api/v1/community": {"get": {"summary": "List approved events and meetups", "parameters": _list_parameters() + [{"name": "type", "in": "query", "schema": {"type": "string", "enum": ["event", "meetup"]}}], "responses": {"200": {"description": "Approved community collection"}, "400": {"description": "Invalid query"}, "404": {"description": "Server is not public"}}}},
            "/status": {"get": {"summary": "Public service status", "responses": {"200": {"description": "Service health without secrets"}}}},
        },
    }


def _list_parameters():
    return [
        {"name": "guild_id", "in": "query", "schema": {"type": "string"}, "description": "Optional public Discord server ID."},
        {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50}},
    ]


def privacy_export(connection, user_id):
    user_id = str(user_id or "")
    result = {"user_id": user_id, "exported_at": utc_now_iso()}
    queries = {
        "media_submissions": ("SELECT id,guild_id,category,status,created_at FROM submissions WHERE user_id=? ORDER BY id", (user_id,)),
        "quotes": ("SELECT id,guild_id,quote_text,speaker,status,created_at FROM community_quotes WHERE submitter_user_id=? ORDER BY id", (user_id,)),
        "community_posts": ("SELECT id,guild_id,post_type,title,status,created_at FROM community_posts WHERE submitter_user_id=? ORDER BY id", (user_id,)),
        "quote_votes": ("SELECT quote_id,vote,created_at,updated_at FROM community_quote_votes WHERE user_id=? ORDER BY quote_id", (user_id,)),
        "notifications": ("SELECT title,body,category,action_url,is_read,created_at FROM user_notifications WHERE user_id=? ORDER BY id", (user_id,)),
        "privacy_requests": ("SELECT request_type,status,created_at,completed_at FROM privacy_requests WHERE user_id=? ORDER BY id", (user_id,)),
    }
    for key, (sql, params) in queries.items():
        result[key] = [dict(row) for row in connection.execute(sql, params).fetchall()]
    return result
