"""Shared quote validation, duplicate detection, and display helpers."""

import hashlib
import re


QUOTE_CATEGORIES = (
    "Community",
    "Funny",
    "Inspirational",
    "Anime",
    "Gaming",
    "Wholesome",
    "Other",
)


def clean_quote_field(value, limit):
    return str(value or "").replace("\x00", "").strip()[: int(limit)]


def normalize_quote_component(value):
    value = clean_quote_field(value, 2000).casefold()
    value = re.sub(r"[\u2018\u2019]", "'", value)
    value = re.sub(r"[\u201c\u201d]", '"', value)
    return " ".join(value.split())


def quote_fingerprint(quote_text, speaker):
    normalized = f"{normalize_quote_component(quote_text)}\n{normalize_quote_component(speaker)}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalized_quote_category(value):
    requested = clean_quote_field(value, 40)
    for category in QUOTE_CATEGORIES:
        if requested.casefold() == category.casefold():
            return category
    return "Community"


def find_duplicate_quote(connection, guild_id, normalized_hash, exclude_id=None):
    params = [str(guild_id), str(normalized_hash)]
    exclude_sql = ""
    if exclude_id is not None:
        exclude_sql = " AND id != ?"
        params.append(int(exclude_id))
    duplicate = connection.execute(
        f"""
        SELECT id, status
        FROM community_quotes
        WHERE guild_id = ? AND normalized_hash = ?
          AND status IN ('pending', 'approved')
          {exclude_sql}
        ORDER BY id ASC
        LIMIT 1
        """,
        tuple(params),
    ).fetchone()
    if duplicate:
        return duplicate
    legacy_params = [str(guild_id)]
    legacy_exclude_sql = ""
    if exclude_id is not None:
        legacy_exclude_sql = " AND id != ?"
        legacy_params.append(int(exclude_id))
    legacy_rows = connection.execute(
        f"""
        SELECT id, status, quote_text, speaker, normalized_hash
        FROM community_quotes
        WHERE guild_id = ? AND status IN ('pending', 'approved')
          {legacy_exclude_sql}
        ORDER BY id ASC
        """,
        tuple(legacy_params),
    ).fetchall()
    for row in legacy_rows:
        existing_hash = row["normalized_hash"] or quote_fingerprint(
            row["quote_text"], row["speaker"]
        )
        if not row["normalized_hash"]:
            connection.execute(
                "UPDATE community_quotes SET normalized_hash = ? WHERE id = ?",
                (existing_hash, int(row["id"])),
            )
        if existing_hash == normalized_hash:
            return row
    return None


def quote_display_text(row):
    quote_text = clean_quote_field(row["quote_text"], 1000)
    speaker = clean_quote_field(row["speaker"], 160)
    lines = [f"“{quote_text}”", f"— **{speaker}**"]
    keys = set(row.keys()) if hasattr(row, "keys") else set(row)
    metadata = []
    if "category" in keys and row["category"]:
        metadata.append(clean_quote_field(row["category"], 40))
    if "source_text" in keys and row["source_text"]:
        metadata.append(f"Source: {clean_quote_field(row['source_text'], 200)}")
    if metadata:
        lines.append(" · ".join(metadata))
    if "context_text" in keys and row["context_text"]:
        lines.append(f"Context: {clean_quote_field(row['context_text'], 300)}")
    return "\n".join(lines)
