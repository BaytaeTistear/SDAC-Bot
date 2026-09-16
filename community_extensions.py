"""Community voting, safety, media privacy, revisions, and webhook helpers."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import re
import socket
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


URL_PATTERN = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
DISCORD_INVITE_PATTERN = re.compile(
    r"(?:discord(?:app)?\.com/invite|discord\.gg)/[A-Za-z0-9-]+", re.IGNORECASE
)
EXECUTABLE_LINK_PATTERN = re.compile(
    r"https?://[^\s<>]+\.(?:exe|msi|bat|cmd|scr|ps1|jar)(?:[?#][^\s<>]*)?$",
    re.IGNORECASE,
)


@contextmanager
def managed_connection(connection_factory):
    connection = connection_factory()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def screen_content(*values):
    """Return structured, explainable findings for user-submitted text."""
    text = "\n".join(str(value or "") for value in values).strip()
    findings = []
    urls = URL_PATTERN.findall(text)
    if DISCORD_INVITE_PATTERN.search(text):
        findings.append({"code": "discord_invite", "severity": "high", "message": "Discord invite link requires review."})
    if any(EXECUTABLE_LINK_PATTERN.match(url.rstrip(".,)")) for url in urls):
        findings.append({"code": "executable_link", "severity": "high", "message": "Executable download link requires review."})
    if len(urls) > 3:
        findings.append({"code": "link_burst", "severity": "medium", "message": "More than three links were submitted."})
    if re.search(r"(.)\1{11,}", text, re.IGNORECASE):
        findings.append({"code": "repetition", "severity": "medium", "message": "Excessive repeated characters were detected."})
    if len(text) >= 80:
        words = re.findall(r"[a-z0-9']+", text.casefold())
        if words and len(set(words)) <= max(2, len(words) // 6):
            findings.append({"code": "repeated_text", "severity": "medium", "message": "Highly repetitive text was detected."})
    return findings


def safety_status(findings):
    return "quarantined" if findings else "pending"


def record_safety_findings(connection, entity_type, entity_id, guild_id, findings):
    if not findings:
        return
    connection.execute(
        """
        INSERT INTO content_safety_flags (
            entity_type, entity_id, guild_id, findings_json, status, created_at
        ) VALUES (?, ?, ?, ?, 'open', ?)
        """,
        (str(entity_type), str(entity_id), str(guild_id or ""), json.dumps(findings, separators=(",", ":")), utc_now_iso()),
    )


def record_revision(connection, entity_type, entity_id, user_id, payload):
    connection.execute(
        """
        INSERT INTO submission_revisions (
            entity_type, entity_id, user_id, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (str(entity_type), str(entity_id), str(user_id or ""), json.dumps(payload, sort_keys=True), utc_now_iso()),
    )


def quote_vote_totals(connection, quote_ids):
    quote_ids = [int(value) for value in quote_ids if str(value).isdigit()]
    if not quote_ids:
        return {}
    placeholders = ",".join("?" for _ in quote_ids)
    rows = connection.execute(
        f"""
        SELECT quote_id, COALESCE(SUM(vote), 0) AS score, COUNT(*) AS vote_count
        FROM community_quote_votes
        WHERE quote_id IN ({placeholders})
        GROUP BY quote_id
        """,
        quote_ids,
    ).fetchall()
    return {int(row["quote_id"]): {"score": int(row["score"] or 0), "vote_count": int(row["vote_count"] or 0)} for row in rows}


def scrub_image_metadata(path):
    """Atomically remove image metadata while preserving orientation; return an action label."""
    target = Path(path)
    if target.suffix.casefold() not in {".jpg", ".jpeg", ".png", ".webp"} or not target.is_file():
        return "skipped"
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return "pillow_unavailable"
    temporary_name = ""
    try:
        with Image.open(target) as source:
            if getattr(source, "is_animated", False):
                return "animated_skipped"
            output = ImageOps.exif_transpose(source)
            if output.mode not in {"RGB", "RGBA", "L"}:
                output = output.convert("RGBA" if "A" in output.getbands() else "RGB")
            suffix = target.suffix.casefold()
            image_format = "JPEG" if suffix in {".jpg", ".jpeg"} else suffix[1:].upper()
            options = {"optimize": True}
            if image_format == "JPEG":
                if output.mode == "RGBA":
                    output = output.convert("RGB")
                options.update({"quality": 92, "progressive": True})
            with tempfile.NamedTemporaryFile(dir=target.parent, suffix=target.suffix, delete=False) as handle:
                temporary_name = handle.name
            output.save(temporary_name, format=image_format, **options)
        Path(temporary_name).replace(target)
        return "scrubbed"
    except Exception:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
        return "failed"


def _public_webhook_url(value):
    try:
        parsed = urlparse(str(value or "").strip())
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return False
        for result in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM):
            address = ipaddress.ip_address(result[4][0])
            if not address.is_global:
                return False
        return True
    except (OSError, ValueError):
        return False


def deliver_webhook_event(connection_factory, event_key, guild_id, payload, event_id="", created_at="", outbox_id=None, return_details=False, target_subscription_id=0):
    """Deliver a signed JSON event to enabled, public HTTPS subscriptions."""
    event_id = str(event_id or hashlib.sha256(f"{event_key}:{guild_id}:{utc_now_iso()}".encode()).hexdigest())
    body = json.dumps({"id": event_id, "event": event_key, "guild_id": str(guild_id or ""), "created_at": created_at or utc_now_iso(), "data": payload}, separators=(",", ":")).encode("utf-8")
    with managed_connection(connection_factory) as connection:
        rows = connection.execute(
            """
            SELECT id, event_url, secret, events_json
            FROM webhook_subscriptions
            WHERE enabled = 1 AND (guild_id = ? OR guild_id = '')
              AND (? = 0 OR id = ?)
            ORDER BY id
            """,
            (str(guild_id or ""), int(target_subscription_id or 0), int(target_subscription_id or 0)),
        ).fetchall()
    delivered = 0
    eligible = 0
    for row in rows:
        try:
            events = json.loads(row["events_json"] or "[]")
        except (TypeError, ValueError):
            events = []
        if events and event_key not in events and "*" not in events:
            continue
        eligible += 1
        status, http_status, error = "failed", 0, ""
        if not _public_webhook_url(row["event_url"]):
            error = "Webhook URL must resolve to a public HTTPS address."
        else:
            signature = hmac.new(str(row["secret"] or "").encode("utf-8"), body, hashlib.sha256).hexdigest()
            try:
                response = urlopen(Request(row["event_url"], data=body, headers={"Content-Type": "application/json", "User-Agent": "Sana-Chan-Webhook/1", "X-SDAC-Event": event_key, "X-SDAC-Signature-256": "sha256=" + signature, "Idempotency-Key": event_id}, method="POST"), timeout=5)
                http_status = int(getattr(response, "status", 200))
                status = "delivered" if 200 <= http_status < 300 else "failed"
                delivered += 1 if status == "delivered" else 0
            except HTTPError as exc:
                http_status, error = int(exc.code), str(exc)[:500]
            except (URLError, OSError, TimeoutError) as exc:
                error = str(exc)[:500]
        with managed_connection(connection_factory) as connection:
            connection.execute(
                """
                INSERT INTO webhook_deliveries (
                    subscription_id, event_key, status, http_status, error_text, created_at,
                    idempotency_key, outbox_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (int(row["id"]), event_key, status, http_status, error, utc_now_iso(), event_id, outbox_id),
            )
            if status == "delivered":
                connection.execute("UPDATE webhook_subscriptions SET consecutive_failures=0,last_success_at=?,disabled_reason='' WHERE id=?", (utc_now_iso(), int(row["id"])))
            else:
                connection.execute("UPDATE webhook_subscriptions SET consecutive_failures=consecutive_failures+1 WHERE id=?", (int(row["id"]),))
                failure_row = connection.execute("SELECT consecutive_failures FROM webhook_subscriptions WHERE id=?", (int(row["id"]),)).fetchone()
                if failure_row and int(failure_row["consecutive_failures"] or 0) >= 10:
                    connection.execute("UPDATE webhook_subscriptions SET enabled=0,disabled_reason='Automatically disabled after 10 consecutive failures' WHERE id=?", (int(row["id"]),))
    return (delivered, eligible) if return_details else delivered


def process_webhook_outbox(connection_factory, limit=20):
    """Deliver due webhook events with bounded exponential retries."""
    from professional_services import schedule_webhook_retry

    now = utc_now_iso()
    with managed_connection(connection_factory) as connection:
        stale_before = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        connection.execute(
            """UPDATE webhook_outbox SET status='retry',next_attempt_at=?,last_error='Recovered stale delivery claim',updated_at=?
               WHERE status='processing' AND updated_at < ?""",
            (now, now, stale_before),
        )
        rows = connection.execute(
            """SELECT * FROM webhook_outbox WHERE status IN ('pending','retry') AND next_attempt_at <= ? ORDER BY id LIMIT ?""",
            (now, int(limit)),
        ).fetchall()
    processed = 0
    for row in rows:
        with managed_connection(connection_factory) as connection:
            claim = connection.execute(
                "UPDATE webhook_outbox SET status='processing',updated_at=? WHERE id=? AND status IN ('pending','retry')",
                (utc_now_iso(), int(row["id"])),
            )
            if int(claim.rowcount or 0) != 1:
                continue
        try:
            payload = json.loads(row["payload_json"] or "{}")
            target_subscription_id = int(payload.get("subscription_id") or 0) if row["event_key"] == "webhook.test" else 0
            delivered, eligible = deliver_webhook_event(
                connection_factory, row["event_key"], row["guild_id"], payload,
                event_id=row["event_id"], created_at=row["created_at"], outbox_id=int(row["id"]), return_details=True,
                target_subscription_id=target_subscription_id,
            )
            with managed_connection(connection_factory) as connection:
                if eligible == 0 or delivered == eligible:
                    connection.execute("UPDATE webhook_outbox SET status='delivered',attempt_count=attempt_count+1,last_error='',updated_at=? WHERE id=?", (utc_now_iso(), int(row["id"])))
                else:
                    schedule_webhook_retry(connection, int(row["id"]), int(row["attempt_count"] or 0) + 1, f"Delivered {delivered} of {eligible} subscriptions")
            processed += 1
        except Exception as exc:
            with managed_connection(connection_factory) as connection:
                schedule_webhook_retry(connection, int(row["id"]), int(row["attempt_count"] or 0) + 1, str(exc))
    return processed
