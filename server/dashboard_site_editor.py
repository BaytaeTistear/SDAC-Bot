"""Per-server Square-style website content editor with restricted HTML blocks."""

import html
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlparse
from uuid import uuid4

from flask import Blueprint, abort, jsonify, redirect, request, session, url_for


DEFAULT_REACTION_ROLE_HELP = "Choose a Discord default emoji below, or enter a Unicode emoji."
PAGE_OPTIONS = {
    "home": {"label": "Submissions home", "endpoint": "index"},
    "about": {"label": "About", "endpoint": "about"},
    "setup": {"label": "Setup guide", "endpoint": "setup_guide"},
    "servers": {"label": "Server directory", "endpoint": "servers"},
    "server_profile": {"label": "Server profile", "endpoint": "server_profile"},
    "stats": {"label": "Public stats", "endpoint": "public_stats"},
    "guessing": {"label": "Guessing leaderboard", "endpoint": "guessing_leaderboard"},
    "achievements": {"label": "Achievements", "endpoint": "achievements"},
    "reaction_roles": {"label": "Reaction Roles", "endpoint": "reaction_roles.manage"},
}
# Only public website routes receive injected content. Reaction Roles uses the
# stored helper copy but its endpoint is an authenticated dashboard tool.
PAGE_BY_ENDPOINT = {
    value["endpoint"]: key
    for key, value in PAGE_OPTIONS.items()
    if key != "reaction_roles"
}
ALLOWED_TAGS = {
    "a", "b", "blockquote", "br", "code", "div", "em", "h2", "h3", "h4",
    "hr", "i", "img", "li", "ol", "p", "pre", "s", "small", "span", "strong", "u", "ul",
}
VOID_TAGS = {"br", "hr", "img"}
SKIP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed", "svg", "math"}


def _safe_link(value, image=False):
    value = str(value or "").strip()
    parsed = urlparse(value)
    allowed = {"https"} if image else {"https", "http", "mailto", "tel"}
    if value.startswith("#") or (value.startswith("/") and not value.startswith("//")):
        return value
    return value if parsed.scheme.casefold() in allowed else ""


class _SafeHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0
        self.open_tags = []

    def handle_starttag(self, tag, attrs):
        tag = tag.casefold()
        if self.skip_depth:
            if tag in SKIP_CONTENT_TAGS:
                self.skip_depth += 1
            return
        if tag in SKIP_CONTENT_TAGS:
            self.skip_depth = 1
            return
        if tag not in ALLOWED_TAGS:
            return
        safe_attrs = []
        attrs = dict(attrs)
        if tag == "a":
            href = _safe_link(attrs.get("href"))
            if href:
                safe_attrs.append(("href", href))
            if attrs.get("title"):
                safe_attrs.append(("title", attrs["title"][:200]))
            if attrs.get("target") == "_blank":
                safe_attrs.extend([("target", "_blank"), ("rel", "noopener noreferrer")])
        elif tag == "img":
            src = _safe_link(attrs.get("src"), image=True)
            if not src:
                return
            safe_attrs.append(("src", src))
            safe_attrs.append(("alt", str(attrs.get("alt", ""))[:300]))
            if attrs.get("title"):
                safe_attrs.append(("title", attrs["title"][:200]))
        serialized = "".join(
            f' {name}="{html.escape(str(value), quote=True)}"'
            for name, value in safe_attrs
        )
        self.parts.append(f"<{tag}{serialized}>")
        if tag not in VOID_TAGS:
            self.open_tags.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.casefold() not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.casefold()
        if self.skip_depth:
            if tag in SKIP_CONTENT_TAGS:
                self.skip_depth -= 1
            return
        if tag not in ALLOWED_TAGS or tag in VOID_TAGS or tag not in self.open_tags:
            return
        while self.open_tags:
            opened = self.open_tags.pop()
            self.parts.append(f"</{opened}>")
            if opened == tag:
                break

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(html.escape(data))

    def close(self):
        super().close()
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")


def sanitize_html(source):
    parser = _SafeHTML()
    parser.feed(str(source or "")[:12000])
    parser.close()
    return "".join(parser.parts)


def _default_page(page_key):
    return {
        "page_heading": "",
        "helper_text": DEFAULT_REACTION_ROLE_HELP if page_key == "reaction_roles" else "",
        "sections": [],
    }


def _decode_page(raw, page_key):
    try:
        value = json.loads(raw or "")
    except (TypeError, json.JSONDecodeError):
        value = None
    return value if isinstance(value, dict) else _default_page(page_key)


def _page_row(connection, guild_id):
    return connection.execute(
        "SELECT draft_json,published_json FROM dashboard_site_pages WHERE guild_id = ?",
        (str(guild_id),),
    ).fetchone()


def _page_data(connection, guild_id, page_key):
    row = _page_row(connection, guild_id)
    if not row:
        default = _default_page(page_key)
        return default, default
    try:
        draft_doc = json.loads(row["draft_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        draft_doc = {}
    try:
        published_doc = json.loads(row["published_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        published_doc = {}
    return (
        draft_doc.get(page_key, _default_page(page_key)),
        published_doc.get(page_key, _default_page(page_key)),
    )


def get_published_page_copy(database, guild_id, page_key, field, default=""):
    if not guild_id:
        return default
    with database() as connection:
        ensure_site_editor_schema(connection)
        _, published = _page_data(connection, guild_id, page_key)
    value = published.get(field, default)
    return value if isinstance(value, str) else default


def ensure_site_editor_schema(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_site_pages (
            guild_id TEXT PRIMARY KEY,
            draft_json TEXT NOT NULL DEFAULT '{}',
            published_json TEXT NOT NULL DEFAULT '{}',
            updated_by TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_site_page_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            page_key TEXT NOT NULL,
            content_json TEXT NOT NULL,
            updated_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_dashboard_site_page_history
        ON dashboard_site_page_history (guild_id, page_key, id DESC)
    """)


def normalize_page_content(raw, page_key, can_use_html, previous):
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("The page draft could not be read. Refresh and try again.") from error
    if not isinstance(payload, dict):
        raise ValueError("Page content must be an object.")
    helper_text = str(payload.get("helper_text", "")).strip()
    page_heading = str(payload.get("page_heading", "")).strip()
    if len(page_heading) > 120:
        raise ValueError("The page heading must be 120 characters or fewer.")
    if len(helper_text) > 300:
        raise ValueError("The helper text must be 300 characters or fewer.")
    sections = payload.get("sections", [])
    if not isinstance(sections, list) or len(sections) > 20:
        raise ValueError("A page can contain up to 20 content sections.")
    old_html = {
        str(item.get("id")): str(item.get("html", ""))
        for item in (previous.get("sections", []) or [])
        if isinstance(item, dict) and item.get("type") == "html"
    }
    normalized = []
    for item in sections:
        if not isinstance(item, dict):
            continue
        section_type = str(item.get("type", "text"))
        if section_type not in {"text", "html"}:
            raise ValueError("Choose a text or HTML content section.")
        section_id = str(item.get("id") or uuid4().hex)[:40]
        section = {"id": section_id, "type": section_type}
        if section_type == "html":
            source = str(item.get("html", ""))
            if len(source) > 12000:
                raise ValueError("HTML sections are limited to 12,000 characters.")
            if not can_use_html and old_html.get(section_id) != source:
                raise ValueError("Only Admin and higher roles can add or change HTML sections.")
            section["html"] = source
        else:
            section["heading"] = str(item.get("heading", "")).strip()[:120]
            section["body"] = str(item.get("body", "")).strip()[:4000]
            section["image_url"] = _safe_link(str(item.get("image_url", "")).strip(), image=True)
            section["button_text"] = str(item.get("button_text", "")).strip()[:80]
            section["button_url"] = _safe_link(item.get("button_url", ""))
        normalized.append(section)
    if not helper_text and page_key == "reaction_roles":
        helper_text = DEFAULT_REACTION_ROLE_HELP
    return {
        "page_heading": page_heading,
        "helper_text": helper_text,
        "sections": normalized,
    }


def render_page_sections(content):
    output = []
    for section in content.get("sections", []):
        if not isinstance(section, dict):
            continue
        if section.get("type") == "html":
            safe_html = sanitize_html(section.get("html", ""))
            if safe_html:
                output.append(f'<section class="sdac-site-section sdac-site-html">{safe_html}</section>')
            continue
        heading = str(section.get("heading", ""))
        body = str(section.get("body", ""))
        image_url = _safe_link(section.get("image_url", ""), image=True)
        button_text = str(section.get("button_text", ""))
        button_url = _safe_link(section.get("button_url", ""))
        parts = ['<section class="sdac-site-section">']
        if heading:
            parts.append(f"<h2>{html.escape(heading)}</h2>")
        if image_url:
            parts.append(f'<img loading="lazy" src="{html.escape(image_url, quote=True)}" alt="{html.escape(heading, quote=True)}">')
        if body:
            parts.append(f'<p>{html.escape(body).replace(chr(10), "<br>")}</p>')
        if button_text and button_url:
            parts.append(f'<p><a href="{html.escape(button_url, quote=True)}">{html.escape(button_text)}</a></p>')
        parts.append("</section>")
        output.append("".join(parts))
    if not output:
        return ""
    return (
        '<div class="sdac-site-content-sections">'
        '<style>.sdac-site-content-sections{max-width:1100px;margin:1rem auto;padding:0 1rem}'
        '.sdac-site-section{margin:1rem 0;padding:1rem;border:1px solid rgba(148,163,184,.25);border-radius:12px}'
        '.sdac-site-section img{display:block;max-width:100%;height:auto;margin:.75rem 0;border-radius:8px}'
        '.sdac-site-section a{color:inherit}</style>'
        + "".join(output)
        + "</div>"
    )


def _editor_body(can_use_html):
    return """
      <style>
        .se-layout{display:grid;grid-template-columns:minmax(280px,1fr) minmax(280px,1fr);gap:16px;align-items:start}
        .se-section{border:1px solid #52627d;border-radius:10px;padding:12px;margin:10px 0;background:#101a2b}
        .se-section label{display:block;margin:8px 0;font-weight:650}
        .se-section input,.se-section textarea{box-sizing:border-box;width:100%;padding:8px;margin-top:4px}
        .se-actions{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
        .se-preview{min-height:160px;border:1px dashed #60718e;border-radius:10px;padding:14px;overflow:auto;background:#0c1423}
        .se-status{color:#aab9ce;font-size:.9rem}
        .se-history-row{align-items:center;display:flex;gap:12px;justify-content:space-between;flex-wrap:wrap}
        .se-toolbar{display:flex;gap:6px;flex-wrap:wrap}
        @media(max-width:760px){.se-layout{grid-template-columns:1fr}}
      </style>
      <h2>Website Editor</h2>
      <p>Build a page from editable text and image sections. Drafts stay private until published. The editor previews the selected server's live page content.</p>
      <form method="get" class="se-toolbar">
        <input type="hidden" name="key" value="{{ admin_key }}">
        <label>Server<select name="guild_id" onchange="this.form.submit()">{% for item in guild_options %}<option value="{{ item.id }}" {% if item.id|string == guild_id|string %}selected{% endif %}>{{ item.name }}</option>{% endfor %}</select></label>
        <label>Page<select name="page" onchange="this.form.submit()">{% for key,label in page_options.items() %}<option value="{{ key }}" {% if key == page_key %}selected{% endif %}>{{ label }}</option>{% endfor %}</select></label>
      </form>
      <div class="se-layout">
        <section>
          <form method="post" id="se-form">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}"><input type="hidden" name="key" value="{{ admin_key }}"><input type="hidden" name="guild_id" value="{{ guild_id }}"><input type="hidden" name="page" value="{{ page_key }}">
            <input type="hidden" name="content_json" id="se-content-json">
            {% if page_key != 'reaction_roles' %}<label>Existing page heading<input id="se-page-heading" maxlength="120" value="{{ draft.page_heading|e }}" placeholder="Leave blank to keep the current heading"></label>{% endif %}
            {% if page_key == 'reaction_roles' %}<label>Emoji and role instructions<input id="se-helper-text" maxlength="300" value="{{ draft.helper_text|e }}"></label>{% endif %}
            <div id="se-sections"></div>
            <div class="se-actions"><button type="button" id="se-add-text">Add text and image section</button>{% if can_use_html %}<button type="button" id="se-add-html">Add HTML section</button>{% endif %}</div>
            <p class="se-status">{% if can_use_html %}HTML is sanitized on publish; scripts, styles, embeds, and unsafe attributes are removed.{% else %}Text and image sections are available. HTML editing requires Admin or higher access on this server.{% endif %}</p>
            <div class="se-actions"><button type="button" id="se-preview">Preview draft</button><button name="action" value="draft">Save draft</button><button name="action" value="publish">Publish changes</button><button name="action" value="reset">Discard draft</button></div>
          </form>
        </section>
        <section><h2>Preview</h2><div class="se-preview" id="se-preview-area">{{ published_preview|safe }}</div></section>
      </div>
      <section class="se-history">
        <h2>Published versions</h2>
        <p class="se-status">Restore a previous published version if a change needs to be undone. Restoring saves the current version in history first.</p>
        {% for version in history %}
          <form method="post" action="{{ url_for('site_editor.restore') }}" class="se-section se-history-row" onsubmit="return confirm('Restore this published version? The current version will remain available in history.');">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}"><input type="hidden" name="key" value="{{ admin_key }}"><input type="hidden" name="guild_id" value="{{ guild_id }}"><input type="hidden" name="page" value="{{ page_key }}"><input type="hidden" name="version_id" value="{{ version.id }}">
            <span>Saved {{ version.created_at }} by {{ version.updated_by or 'admin' }}</span><button type="submit">Restore</button>
          </form>
        {% else %}<p class="se-status">No earlier published versions yet. A snapshot is saved each time a page is published.</p>{% endfor %}
      </section>
      <script type="application/json" id="se-initial">{{ draft|tojson }}</script>
      <script>
      (() => {
        const initial = JSON.parse(document.getElementById('se-initial').textContent || '{}');
        const list = document.getElementById('se-sections');
        const form = document.getElementById('se-form');
        const payloadInput = document.getElementById('se-content-json');
        const htmlAllowed = {{ 'true' if can_use_html else 'false' }};
        const csrfToken = {{ csrf_token|tojson }};
        const pageHeading = document.getElementById('se-page-heading');
        const helper = document.getElementById('se-helper-text');
        const escapeText = (value) => String(value || '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
        const block = (value = {type:'text'}) => {
          const card = document.createElement('article');
          card.className = 'se-section';
          card.dataset.id = value.id || `section-${crypto.randomUUID()}`;
          card.dataset.type = value.type || 'text';
          if (card.dataset.type === 'html') {
            const label = document.createElement('label'); label.textContent = 'HTML source';
            const textarea = document.createElement('textarea'); textarea.rows = 10; textarea.dataset.field = 'html'; textarea.value = value.html || ''; textarea.readOnly = !htmlAllowed;
            card.append(label, textarea);
          } else {
            for (const [name, title, rows] of [['heading','Section heading',1],['body','Text',5],['image_url','Image URL (optional)',1],['button_text','Button label (optional)',1],['button_url','Button link (optional)',1]]) {
              const label = document.createElement('label'); label.textContent = title;
              const input = rows > 1 ? document.createElement('textarea') : document.createElement('input');
              if (rows > 1) input.rows = rows;
              input.dataset.field = name; input.value = value[name] || '';
              label.appendChild(input); card.appendChild(label);
            }
          }
          const toolbar = document.createElement('div'); toolbar.className = 'se-toolbar';
          for (const [text,delta] of [['Move up',-1],['Move down',1]]) { const button=document.createElement('button'); button.type='button'; button.textContent=text; button.addEventListener('click',()=>{const sibling=delta<0?card.previousElementSibling:card.nextElementSibling;if(sibling)list.insertBefore(card,delta<0?sibling: sibling.nextElementSibling);});toolbar.appendChild(button); }
          const remove = document.createElement('button'); remove.type='button'; remove.textContent='Remove section'; remove.addEventListener('click',()=>card.remove()); toolbar.appendChild(remove); card.appendChild(toolbar); list.appendChild(card);
        };
        const collect = () => ({page_heading:pageHeading?pageHeading.value:'',helper_text:helper?helper.value:'',sections:[...list.children].map(card=>({id:card.dataset.id,type:card.dataset.type,...Object.fromEntries([...card.querySelectorAll('[data-field]')].map(field=>[field.dataset.field,field.value]))}))});
        const draw = (data) => {list.replaceChildren();(data.sections||[]).forEach(block);if(pageHeading)pageHeading.value=data.page_heading||'';if(helper)helper.value=data.helper_text||'';};
        draw(initial);
        document.getElementById('se-add-text').addEventListener('click',()=>block({type:'text'}));
        const htmlButton=document.getElementById('se-add-html');if(htmlButton)htmlButton.addEventListener('click',()=>block({type:'html'}));
        form.addEventListener('submit',(event)=>{const submitter=event.submitter;if(submitter&&submitter.value==='reset'){if(!confirm('Discard this page draft and restore the published version?')){event.preventDefault();return;}}payloadInput.value=JSON.stringify(collect());});
        document.getElementById('se-preview').addEventListener('click',async()=>{
          const body=new URLSearchParams({csrf_token:csrfToken,guild_id:{{ guild_id|tojson }},page:{{ page_key|tojson }},content_json:JSON.stringify(collect())});
          const button=document.getElementById('se-preview');button.disabled=true;
          try{const response=await fetch({{ url_for('site_editor.preview')|tojson }},{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});const result=await response.json();if(!response.ok)throw new Error(result.error||'Preview failed.');document.getElementById('se-preview-area').innerHTML=result.html||'<p>No sections to preview.</p>';}
          catch(error){alert(error.message);}finally{button.disabled=false;}
        });
      })();
      </script>
    """


def create_site_editor_blueprint(deps):
    bp = Blueprint("site_editor", __name__)

    def require_editor(guild_id):
        # Authenticate the dashboard account here; the selected guild's
        # minimum role is checked immediately below so per-server access works
        # even if this account has a lower role on its currently selected guild.
        response = deps["require_admin_login"]("user")
        if response:
            return response
        if not deps["can_access"](guild_id):
            abort(403)
        return None

    def selected_server(config_data):
        options = deps["guild_options"](config_data, minimum_role="moderator")
        allowed = {str(item["id"]) for item in options}
        requested = str(request.values.get("guild_id", ""))
        guild_id = requested if requested in allowed else (str(options[0]["id"]) if options else "")
        return options, guild_id

    def read_documents(connection, guild_id):
        ensure_site_editor_schema(connection)
        row = _page_row(connection, guild_id)
        if not row:
            return {}, {}
        try:
            return json.loads(row["draft_json"] or "{}"), json.loads(row["published_json"] or "{}")
        except json.JSONDecodeError:
            return {}, {}

    def write_documents(connection, guild_id, draft_doc, published_doc, actor_id):
        ensure_site_editor_schema(connection)
        connection.execute(
            "INSERT INTO dashboard_site_pages (guild_id,draft_json,published_json,updated_by,updated_at) "
            "VALUES (?,?,?,?,?) ON CONFLICT(guild_id) DO UPDATE SET "
            "draft_json=excluded.draft_json,published_json=excluded.published_json,"
            "updated_by=excluded.updated_by,updated_at=excluded.updated_at",
            (str(guild_id), json.dumps(draft_doc, ensure_ascii=False),
             json.dumps(published_doc, ensure_ascii=False), str(actor_id), deps["utc_now_iso"]()),
        )

    @bp.route("/admin/website-editor", methods=["GET", "POST"])
    def manage():
        config_data = deps["load_config"]()
        options, guild_id = selected_server(config_data)
        if not guild_id:
            return deps["admin_tool_shell"](
                "Website Editor", "Edit server website sections and page text.",
                "<p>No moderator-accessible servers are available for this account.</p>",
            )
        response = require_editor(guild_id)
        if response:
            return response
        page_key = str(request.values.get("page", "home"))
        if page_key not in PAGE_OPTIONS:
            abort(404)
        can_use_html = bool(deps["can_edit_html"](guild_id))
        if request.method == "POST":
            deps["require_csrf_token"]()
            action = request.form.get("action", "draft")
            actor_id, actor_name = deps["web_actor"]()
            with deps["database"]() as connection:
                draft_doc, published_doc = read_documents(connection, guild_id)
                old_page = draft_doc.get(page_key, _default_page(page_key))
                if action == "reset":
                    draft_doc[page_key] = published_doc.get(page_key, _default_page(page_key))
                    notice = "Draft discarded; published content restored."
                    audit_action = "website_page_draft_discarded"
                else:
                    if action not in {"publish", "draft"}:
                        return redirect(url_for("site_editor.manage", key=deps["ADMIN_KEY"], guild_id=guild_id, page=page_key, notice="Unknown editor action.", error=1))
                    try:
                        normalized = normalize_page_content(
                            request.form.get("content_json", "{}"), page_key, can_use_html, old_page,
                        )
                    except ValueError as error:
                        return redirect(url_for("site_editor.manage", key=deps["ADMIN_KEY"], guild_id=guild_id, page=page_key, notice=str(error), error=1))
                    if action == "publish":
                        old_published = published_doc.get(page_key, _default_page(page_key))
                        if old_published != normalized:
                            ensure_site_editor_schema(connection)
                            connection.execute(
                                "INSERT INTO dashboard_site_page_history (guild_id,page_key,content_json,updated_by,created_at) VALUES (?,?,?,?,?)",
                                (str(guild_id), page_key, json.dumps(old_published, ensure_ascii=False), str(actor_name), deps["utc_now_iso"]()),
                            )
                            connection.execute(
                                "DELETE FROM dashboard_site_page_history WHERE guild_id = ? AND page_key = ? AND id NOT IN (SELECT id FROM dashboard_site_page_history WHERE guild_id = ? AND page_key = ? ORDER BY id DESC LIMIT 20)",
                                (str(guild_id), page_key, str(guild_id), page_key),
                            )
                        draft_doc[page_key] = normalized
                        published_doc[page_key] = normalized
                        notice = "Website page published."
                        audit_action = "website_page_published"
                    else:
                        draft_doc[page_key] = normalized
                        notice = "Draft saved. It is not visible to visitors until published."
                        audit_action = "website_page_draft_saved"
                write_documents(connection, guild_id, draft_doc, published_doc, actor_id)
                deps["add_admin_audit_log"](
                    connection, guild_id, audit_action, actor_id, actor_name,
                    "website_page", page_key, f"page={page_key}; sections={len(draft_doc[page_key].get('sections', []))}",
                )
            return redirect(url_for("site_editor.manage", key=deps["ADMIN_KEY"], guild_id=guild_id, page=page_key, notice=notice))

        with deps["database"]() as connection:
            draft_doc, published_doc = read_documents(connection, guild_id)
            ensure_site_editor_schema(connection)
            history = connection.execute(
                "SELECT id,updated_by,created_at FROM dashboard_site_page_history WHERE guild_id = ? AND page_key = ? ORDER BY id DESC LIMIT 20",
                (str(guild_id), page_key),
            ).fetchall()
        draft = draft_doc.get(page_key, _default_page(page_key))
        published = published_doc.get(page_key, _default_page(page_key))
        preview = (
            f'<h2>{html.escape(published.get("page_heading", ""))}</h2>'
            if published.get("page_heading") else ""
        ) + render_page_sections(published)
        if page_key == "reaction_roles":
            preview = f'<p>{html.escape(published.get("helper_text", DEFAULT_REACTION_ROLE_HELP))}</p>' + preview
        body = _editor_body(can_use_html)
        return deps["admin_tool_shell"](
            "Website Editor", "Build server website pages from editable sections, preview drafts, and publish when ready.",
            body, guild_options=options, guild_id=guild_id, page_key=page_key,
            page_options={key: value["label"] for key, value in PAGE_OPTIONS.items()},
            draft=draft, published_preview=preview, can_use_html=can_use_html,
            history=history,
        )

    @bp.route("/admin/website-editor/restore", methods=["POST"])
    def restore():
        deps["require_csrf_token"]()
        guild_id = str(request.form.get("guild_id", ""))
        response = require_editor(guild_id)
        if response:
            return response
        page_key = str(request.form.get("page", ""))
        version_id = str(request.form.get("version_id", ""))
        if page_key not in PAGE_OPTIONS or not version_id.isdigit():
            abort(400, "Choose a valid page version.")
        actor_id, actor_name = deps["web_actor"]()
        with deps["database"]() as connection:
            ensure_site_editor_schema(connection)
            row = connection.execute(
                "SELECT content_json FROM dashboard_site_page_history WHERE id = ? AND guild_id = ? AND page_key = ?",
                (int(version_id), guild_id, page_key),
            ).fetchone()
            if not row:
                abort(404)
            try:
                restored = json.loads(row["content_json"])
            except (TypeError, json.JSONDecodeError):
                abort(400, "That saved version is unreadable.")
            if not isinstance(restored, dict):
                abort(400, "That saved version is invalid.")
            if any(isinstance(item, dict) and item.get("type") == "html" for item in restored.get("sections", [])) and not deps["can_edit_html"](guild_id):
                abort(403)
            draft_doc, published_doc = read_documents(connection, guild_id)
            current = published_doc.get(page_key, _default_page(page_key))
            connection.execute(
                "INSERT INTO dashboard_site_page_history (guild_id,page_key,content_json,updated_by,created_at) VALUES (?,?,?,?,?)",
                (guild_id, page_key, json.dumps(current, ensure_ascii=False), str(actor_name), deps["utc_now_iso"]()),
            )
            connection.execute(
                "DELETE FROM dashboard_site_page_history WHERE guild_id = ? AND page_key = ? AND id NOT IN (SELECT id FROM dashboard_site_page_history WHERE guild_id = ? AND page_key = ? ORDER BY id DESC LIMIT 20)",
                (guild_id, page_key, guild_id, page_key),
            )
            published_doc[page_key] = restored
            draft_doc[page_key] = restored
            write_documents(connection, guild_id, draft_doc, published_doc, actor_id)
            deps["add_admin_audit_log"](
                connection, guild_id, "website_page_version_restored", actor_id, actor_name,
                "website_page", page_key, f"restored_version={version_id}",
            )
        return redirect(url_for("site_editor.manage", key=deps["ADMIN_KEY"], guild_id=guild_id, page=page_key, notice="Published version restored."))

    @bp.route("/admin/website-editor/preview", methods=["POST"])
    def preview():
        deps["require_csrf_token"]()
        guild_id = str(request.form.get("guild_id", ""))
        response = require_editor(guild_id)
        if response:
            return response
        page_key = str(request.form.get("page", ""))
        if page_key not in PAGE_OPTIONS:
            return jsonify(error="Choose a valid page."), 400
        can_use_html = bool(deps["can_edit_html"](guild_id))
        with deps["database"]() as connection:
            draft_doc, _ = read_documents(connection, guild_id)
        try:
            content = normalize_page_content(
                request.form.get("content_json", "{}"), page_key, can_use_html,
                draft_doc.get(page_key, _default_page(page_key)),
            )
        except ValueError as error:
            return jsonify(error=str(error)), 400
        result = render_page_sections(content)
        if content.get("page_heading"):
            result = f'<h2>{html.escape(content["page_heading"])}</h2>' + result
        if page_key == "reaction_roles":
            result = f'<p>{html.escape(content.get("helper_text", ""))}</p>' + result
        return jsonify(html=result)

    @bp.after_app_request
    def inject_published_sections(response):
        page_key = PAGE_BY_ENDPOINT.get(request.endpoint or "")
        if (
            page_key is None
            or not response.mimetype or response.mimetype != "text/html"
            or request.endpoint in {"site_editor.manage", "site_editor.preview"}
        ):
            return response

        view_args = request.view_args or {}
        requested_guild = (
            request.args.get("guild_id")
            or view_args.get("guild_id")
            or session.get("sdac_guild_id")
            or ""
        )
        guild_id = str(requested_guild)
        if guild_id == "all":
            guild_id = ""

        editor_guild_id = ""
        if deps["is_admin_logged_in"]():
            editor_servers = deps["guild_options"](
                deps["load_config"](), minimum_role="admin",
            )
            editor_ids = {str(item["id"]) for item in editor_servers}
            if guild_id:
                if guild_id in editor_ids and deps["can_edit_html"](guild_id):
                    editor_guild_id = guild_id
            elif editor_servers:
                editor_guild_id = str(editor_servers[0]["id"])

        if not guild_id and editor_guild_id:
            guild_id = editor_guild_id

        try:
            body = response.get_data(as_text=True)

            if guild_id:
                with deps["database"]() as connection:
                    ensure_site_editor_schema(connection)
                    _, published_doc = read_documents(connection, guild_id)
                content = published_doc.get(page_key, _default_page(page_key))
                page_heading = str(content.get("page_heading", "")).strip()
                if page_heading:
                    body = re.sub(
                        r"(<h1\b[^>]*>).*?(</h1>)",
                        lambda match: match.group(1) + html.escape(page_heading) + match.group(2),
                        body,
                        count=1,
                        flags=re.IGNORECASE | re.DOTALL,
                    )
                fragment = render_page_sections(content)
                if fragment:
                    if "</main>" in body:
                        body = body.replace("</main>", fragment + "</main>", 1)
                    elif "</body>" in body:
                        body = body.replace("</body>", fragment + "</body>", 1)

            if editor_guild_id:
                editor_url = url_for(
                    "site_editor.manage", key=deps["ADMIN_KEY"],
                    guild_id=editor_guild_id, page=page_key,
                )
                button = (
                    '<a class="sdac-edit-this-page" href="'
                    + html.escape(editor_url, quote=True)
                    + '">Edit This Page</a>'
                    '<style>.sdac-edit-this-page{position:fixed;top:16px;right:16px;z-index:99999;'
                    'display:inline-flex;align-items:center;justify-content:center;padding:10px 16px;'
                    'border:1px solid rgba(255,255,255,.25);border-radius:10px;background:linear-gradient(110deg,#7357ff,#14c9ee);'
                    'box-shadow:0 6px 22px rgba(0,0,0,.3);color:#fff;font:700 14px/1.2 system-ui,sans-serif;'
                    'text-decoration:none}.sdac-edit-this-page:hover{filter:brightness(1.08)}'
                    '@media(max-width:600px){.sdac-edit-this-page{top:10px;right:10px;padding:8px 11px;font-size:12px}}</style>'
                )
                body_match = re.search(r"<body\b[^>]*>", body, re.IGNORECASE)
                if body_match:
                    body = body[:body_match.end()] + button + body[body_match.end():]
                elif "</body>" in body:
                    body = body.replace("</body>", button + "</body>", 1)

            response.set_data(body)
        except Exception as error:
            print(f"Website content could not be rendered for {guild_id}/{page_key}: {error}", flush=True)
        return response

    return bp
