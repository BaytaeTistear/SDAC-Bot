#!/usr/bin/env python3
import argparse
import gzip
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


APP_DIR = Path(os.getenv("SDAC_APP_DIR", Path.cwd())).resolve()
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from database_backend import connect_database


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def month_cutoff(months):
    now = datetime.now(timezone.utc)
    cutoff_year = now.year
    cutoff_month = now.month - months
    while cutoff_month <= 0:
        cutoff_month += 12
        cutoff_year -= 1
    return f"{cutoff_year:04d}-{cutoff_month:02d}"


def row_dict(row):
    return {key: row[key] for key in row.keys()}


def preserve_monthly_top(connection, month):
    existing = connection.execute("""
        SELECT 1
        FROM monthly_submission_top
        WHERE month = ?
        LIMIT 1
    """, (month,)).fetchone()
    if existing:
        return
    rows = connection.execute("""
        SELECT *
        FROM submissions
        WHERE status = 'posted'
          AND substr(COALESCE(created_at, submitted_at), 1, 7) = ?
        ORDER BY category ASC, stars DESC, created_at DESC, id DESC
    """, (month,)).fetchall()
    ranks = {}
    captured_at = utc_now_iso()
    for row in rows:
        category = row["category"] or "Uncategorized"
        rank = ranks.get(category, 0) + 1
        if rank > 10:
            continue
        ranks[category] = rank
        connection.execute("""
            INSERT OR IGNORE INTO monthly_submission_top (
                month, category, rank, submission_id, guild_id,
                original_message_id, repost_message_id, repost_channel_id,
                user_id, username, message_text, file_paths, media_paths,
                media_names, media_types, media_sizes, media_metadata_json,
                stars, voters, submitted_at, created_at, captured_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            month,
            category,
            rank,
            row["id"],
            row["guild_id"],
            row["original_message_id"],
            row["repost_message_id"],
            row["repost_channel_id"],
            row["user_id"],
            row["username"],
            row["message_text"],
            row["file_paths"],
            row["media_paths"],
            row["media_names"],
            row["media_types"],
            row["media_sizes"],
            row["media_metadata_json"],
            row["stars"] or 0,
            row["voters"],
            row["submitted_at"],
            row["created_at"],
            captured_at,
        ))


def main():
    parser = argparse.ArgumentParser(
        description="Archive old SDAC submission history to compressed JSON."
    )
    parser.add_argument("--months", type=int, default=18)
    parser.add_argument("--delete-exported", action="store_true")
    parser.add_argument("--db", default=os.getenv("SDAC_DB_FILE", str(APP_DIR / "sdac.db")))
    parser.add_argument(
        "--out-dir",
        default=os.getenv("SDAC_HISTORY_ARCHIVE_DIR", str(APP_DIR / "backups" / "history-archives")),
    )
    args = parser.parse_args()
    months = max(1, args.months)
    cutoff = month_cutoff(months)
    db_path = Path(args.db)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_path = out_dir / (
        f"submissions-before-{cutoff}"
        f"{'-removed' if args.delete_exported else ''}.json.gz"
    )

    connection = connect_database(db_path, timeout=30)
    try:
        month_rows = connection.execute("""
            SELECT DISTINCT substr(COALESCE(created_at, submitted_at), 1, 7) AS month
            FROM submissions
            WHERE COALESCE(created_at, submitted_at, '') != ''
              AND substr(COALESCE(created_at, submitted_at), 1, 7) < ?
            ORDER BY month
        """, (cutoff,)).fetchall()
        for row in month_rows:
            preserve_monthly_top(connection, row["month"])
        rows = connection.execute("""
            SELECT *
            FROM submissions
            WHERE COALESCE(created_at, submitted_at, '') != ''
              AND substr(COALESCE(created_at, submitted_at), 1, 7) < ?
            ORDER BY created_at, id
        """, (cutoff,)).fetchall()
        payload = {
            "created_at": utc_now_iso(),
            "cutoff_month": cutoff,
            "delete_exported": args.delete_exported,
            "rows": [row_dict(row) for row in rows],
        }
        with gzip.open(archive_path, "wt", encoding="utf-8") as archive_file:
            json.dump(payload, archive_file, indent=2)
            archive_file.write("\n")
        if args.delete_exported and rows:
            connection.execute("""
                DELETE FROM submissions
                WHERE COALESCE(created_at, submitted_at, '') != ''
                  AND substr(COALESCE(created_at, submitted_at), 1, 7) < ?
            """, (cutoff,))
        connection.commit()
    finally:
        connection.close()

    action = "archived and removed" if args.delete_exported else "archived"
    print(f"{action} {len(rows)} row(s) before {cutoff}: {archive_path}")


if __name__ == "__main__":
    main()
