import os
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, abort, redirect, render_template_string, request, send_from_directory, url_for

try:
    from config import TOKEN
except Exception:
    TOKEN = os.getenv("DISCORD_TOKEN", "")


app = Flask(__name__)

ADMIN_KEY = "ImTheBestAdmin"
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "sdac.db"
MEDIA_DIR = (BASE_DIR / "media").resolve()


HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Dashboard</title>
    <style>
        :root {
            color-scheme: dark;
            --bg: #101114;
            --panel: #1b1d22;
            --border: #30333b;
            --muted: #a8adb8;
            --accent: #7c9cff;
            --danger: #e45d68;
        }

        * { box-sizing: border-box; }

        body {
            font-family: Arial, sans-serif;
            background: var(--bg);
            color: #f4f5f7;
            margin: 0;
            padding: 24px;
        }

        main {
            width: min(100%, 1000px);
            margin: 0 auto;
        }

        h1, h2 { text-align: center; }
        h1 { margin-bottom: 8px; }

        .mode {
            color: var(--muted);
            text-align: center;
            margin: 0 0 24px;
        }

        .mode strong { color: var(--accent); }

        .filter {
            display: flex;
            justify-content: center;
            margin-bottom: 30px;
        }

        .filter form {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            justify-content: center;
        }

        select, button {
            border: 1px solid var(--border);
            border-radius: 7px;
            padding: 10px 12px;
            font-size: 16px;
        }

        button {
            background: var(--accent);
            color: #0b1020;
            cursor: pointer;
            font-weight: bold;
        }

        .section { margin-bottom: 40px; }

        .post {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            margin: 14px 0;
        }

        .post-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }

        .meta {
            color: var(--muted);
            font-size: 14px;
        }

        .stars {
            color: #ffd75e;
            font-weight: bold;
        }

        .message {
            margin-top: 12px;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
        }

        .media-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 12px;
            margin-top: 14px;
        }

        .media-grid img,
        .media-grid video {
            background: #090a0c;
            border-radius: 8px;
            display: block;
            max-height: 600px;
            object-fit: contain;
            width: 100%;
        }

        .media-grid audio { width: 100%; }

        .download {
            color: var(--accent);
            overflow-wrap: anywhere;
        }

        .delete-button {
            background: var(--danger);
            border-color: var(--danger);
            color: white;
            font-size: 13px;
            padding: 7px 10px;
        }

        .notice {
            border: 1px solid var(--border);
            border-radius: 8px;
            margin: 0 auto 20px;
            padding: 12px;
            text-align: center;
        }

        .notice.error { border-color: var(--danger); }
        .empty { color: var(--muted); margin-top: 40px; text-align: center; }
    </style>
</head>
<body>
<main>
    <h1>SDAC Dashboard</h1>
    <p class="mode">
        {% if is_admin %}
            <strong>Admin mode</strong>
        {% else %}
            Public gallery
        {% endif %}
    </p>

    {% if notice %}
        <div class="notice {{ 'error' if error else '' }}">{{ notice }}</div>
    {% endif %}

    <div class="filter">
        <form method="get" action="{{ url_for('index') }}">
            {% if is_admin %}
                <input type="hidden" name="key" value="{{ admin_key }}">
            {% endif %}
            <select name="category" aria-label="Category">
                <option value="">All Categories</option>
                {% for cat in categories %}
                    <option value="{{ cat }}" {% if selected_category == cat %}selected{% endif %}>
                        {{ cat }}
                    </option>
                {% endfor %}
            </select>
            <button type="submit">Filter</button>
        </form>
    </div>

    {% if grouped_posts %}
        {% for category, category_posts in grouped_posts.items() %}
            <section class="section">
                <h2>{{ category }}</h2>
                {% for post in category_posts %}
                    <article class="post">
                        <div class="post-header">
                            <div class="meta">
                                {{ post.username }}
                                &middot; {{ post.category }}
                                &middot; <span class="stars">{{ post.stars or 0 }} stars</span>
                            </div>
                            {% if is_admin %}
                                <form method="post"
                                      action="{{ url_for('delete_submission', submission_id=post.id, key=admin_key, category=selected_category) }}"
                                      onsubmit="return confirm('Remove this submission from the website and Discord?');">
                                    <button class="delete-button" type="submit">Remove</button>
                                </form>
                            {% endif %}
                        </div>

                        {% if post.message_text %}
                            <div class="message">{{ post.message_text }}</div>
                        {% endif %}

                        {% if post.media %}
                            <div class="media-grid">
                                {% for item in post.media %}
                                    <div>
                                        {% if item.type == "image" %}
                                            <a href="{{ item.url }}" target="_blank" rel="noopener">
                                                <img src="{{ item.url }}" alt="{{ item.name }}" loading="lazy">
                                            </a>
                                        {% elif item.type == "video" %}
                                            <video src="{{ item.url }}" controls preload="metadata"></video>
                                        {% elif item.type == "audio" %}
                                            <audio src="{{ item.url }}" controls preload="metadata"></audio>
                                        {% else %}
                                            <a class="download" href="{{ item.url }}" download>{{ item.name }}</a>
                                        {% endif %}
                                    </div>
                                {% endfor %}
                            </div>
                        {% endif %}
                    </article>
                {% endfor %}
            </section>
        {% endfor %}
    {% else %}
        <div class="empty">
            {% if selected_category %}
                No posts in this category.
            {% else %}
                No SDAC submissions yet.
            {% endif %}
        </div>
    {% endif %}
</main>
</body>
</html>
"""


def get_db():
    db = sqlite3.connect(DB_FILE, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def split_values(raw_value):
    if not raw_value:
        return []
    return [value for value in raw_value.split(";") if value]


def media_relative_path(stored_path):
    path = Path(stored_path)
    parts = list(path.parts)

    if "media" in parts:
        parts = parts[parts.index("media") + 1:]

    if not parts:
        return None

    relative_path = Path(*parts)
    resolved_path = (MEDIA_DIR / relative_path).resolve()

    try:
        resolved_path.relative_to(MEDIA_DIR)
    except ValueError:
        return None

    return relative_path.as_posix()


def prepare_post(row):
    post = dict(row)
    paths = split_values(post.get("media_paths") or post.get("file_paths"))
    names = split_values(post.get("media_names"))
    types = split_values(post.get("media_types"))
    media = []

    for index, stored_path in enumerate(paths):
        relative_path = media_relative_path(stored_path)
        if not relative_path:
            continue

        media.append({
            "name": names[index] if index < len(names) else Path(relative_path).name,
            "type": types[index] if index < len(types) else "unknown",
            "url": url_for("serve_media", filename=relative_path),
        })

    post["media"] = media
    return post


def delete_discord_repost(channel_id, message_id):
    if not channel_id or not message_id:
        return True, ""

    channel_id = str(channel_id)
    message_id = str(message_id)
    if not channel_id.isdigit() or not message_id.isdigit():
        return False, "The stored Discord message information is invalid."

    if not TOKEN or TOKEN == "YOUR_NEW_TOKEN_HERE":
        return False, "The dashboard has no Discord bot token, so the repost was not deleted."

    api_url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
    api_request = Request(
        api_url,
        method="DELETE",
        headers={
            "Authorization": f"Bot {TOKEN}",
            "User-Agent": "SDAC-Dashboard/1.0",
        },
    )

    try:
        with urlopen(api_request, timeout=15) as response:
            if response.status == 204:
                return True, ""
            return False, f"Discord returned status {response.status}."
    except HTTPError as exc:
        if exc.code == 404:
            return True, ""
        if exc.code == 403:
            return False, "Discord refused the deletion. Check the bot's channel permissions."
        return False, f"Discord returned status {exc.code}."
    except (URLError, TimeoutError):
        return False, "Discord could not be reached. The submission was not removed."


def delete_local_media(row):
    stored_paths = split_values(row["media_paths"] or row["file_paths"])

    for stored_path in stored_paths:
        relative_path = media_relative_path(stored_path)
        if not relative_path:
            continue

        file_path = (MEDIA_DIR / relative_path).resolve()
        if file_path.is_file():
            try:
                file_path.unlink()
            except OSError:
                pass


@app.route("/")
def index():
    selected_category = request.args.get("category", "").strip()
    is_admin = request.args.get("key") == ADMIN_KEY
    notice = request.args.get("notice", "")
    error = request.args.get("error") == "1"

    with closing(get_db()) as db:
        categories = [
            row["category"]
            for row in db.execute("""
                SELECT DISTINCT category
                FROM submissions
                WHERE category IS NOT NULL AND category != ''
                ORDER BY category
            """)
        ]

        if selected_category:
            rows = db.execute("""
                SELECT *
                FROM submissions
                WHERE category = ?
                ORDER BY stars DESC, created_at DESC
            """, (selected_category,)).fetchall()
        else:
            rows = db.execute("""
                SELECT *
                FROM submissions
                ORDER BY category ASC, stars DESC, created_at DESC
            """).fetchall()

    grouped_posts = {}
    for row in rows:
        post = prepare_post(row)
        category = post["category"] or "Uncategorized"
        grouped_posts.setdefault(category, []).append(post)

    return render_template_string(
        HTML,
        admin_key=ADMIN_KEY,
        categories=categories,
        error=error,
        grouped_posts=grouped_posts,
        is_admin=is_admin,
        notice=notice,
        selected_category=selected_category,
    )


@app.route("/media/<path:filename>")
def serve_media(filename):
    resolved_path = (MEDIA_DIR / filename).resolve()

    try:
        resolved_path.relative_to(MEDIA_DIR)
    except ValueError:
        abort(404)

    return send_from_directory(MEDIA_DIR, filename)


@app.post("/delete/<int:submission_id>")
def delete_submission(submission_id):
    if request.args.get("key") != ADMIN_KEY:
        abort(403)

    selected_category = request.args.get("category", "").strip()

    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()

        if not row:
            return redirect(url_for(
                "index",
                key=ADMIN_KEY,
                category=selected_category,
                notice="Submission not found.",
                error=1,
            ))

        deleted, error_message = delete_discord_repost(
            row["repost_channel_id"],
            row["repost_message_id"],
        )

        if not deleted:
            return redirect(url_for(
                "index",
                key=ADMIN_KEY,
                category=selected_category,
                notice=error_message,
                error=1,
            ))

        db.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))
        db.commit()
        delete_local_media(row)

        return redirect(url_for(
            "index",
            key=ADMIN_KEY,
            category=selected_category,
            notice="Submission removed from the website and Discord.",
        ))
    finally:
        db.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
