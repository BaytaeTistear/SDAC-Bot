"""Sidebar section definitions and HTML rendering for the SDAC dashboard."""

import html

from flask import request, session, url_for


ADMIN_SECTIONS = [
    {
        "label": "User",
        "required_role": "user",
        "links": [
            ("Staff Home", "admin_staff_home", {}),
            ("Submissions", "index", {}),
            ("My Submissions", "my_submissions", {}),
            ("Guessing", "guessing_leaderboard", {}),
            ("Servers", "servers", {}),
            ("Stats", "public_stats", {}),
            ("Achievements", "achievements", {}),
        ],
    },
    {
        "label": "Moderator",
        "required_role": "moderator",
        "links": [
            ("Review Queue", "admin_moderation", {}),
            ("Removal Reasons", "admin_removal_reasons", {}),
            ("Users", "admin_users", {}),
            ("Polls", "admin_polls", {}),
            ("Audit", "audit_log", {}),
            ("Anime Activities", "admin_anime_activities", {}),
            ("Metrics", "admin_overview", {}),
        ],
    },
    {
        "label": "Server Owner",
        "required_role": "owner",
        "links": [
            ("Setup Checklist", "admin_setup_checklist", {}),
            ("Categories", "admin_category_manager", {}),
            ("Permissions", "admin_permission_health", {}),
            ("Settings", "admin_settings", {}),
            ("Server Health", "admin_server_health_cards", {}),
            ("Media", "admin_media_cleanup", {}),
            ("Game Library", "admin_game_library", {}),
            ("Seasons", "admin_seasons", {}),
            ("Theme", "admin_theme", {}),
            ("Layout", "admin_layout", {}),
            ("Onboarding", "admin_onboarding", {}),
            ("Privacy", "admin_privacy", {}),
            ("Owner Portal", "admin_owner_portal", {}),
        ],
    },
    {
        "label": "Bot Owner",
        "required_role": "bot_owner",
        "links": [
            ("Global Control", "admin_global_control", {}),
            ("Maintenance Mode", "admin_maintenance_mode", {}),
            ("Config History", "admin_config_history", {}),
            ("Maintenance", "admin_maintenance", {}),
            ("Optimization", "admin_optimization", {}),
            ("Releases", "admin_releases", {}),
            ("Release Checklist", "admin_release_checklist", {}),
            ("Go Live Checklist", "admin_go_live_checklist", {}),
            ("Production", "admin_production_health", {}),
            ("Install Doctor", "admin_install_doctor", {}),
            ("UI Health", "admin_ui_health", {}),
            ("Approvals", "admin_approvals", {}),
            ("Jobs", "admin_jobs", {}),
            ("Analytics", "admin_analytics", {}),
            ("Monthly Report", "admin_monthly_report", {}),
            ("Server Switcher", "admin_server_switcher", {}),
            ("Preview As", "admin_preview_as", {}),
            ("All Submissions", "index", {"guild_id": "all"}),
            ("All Guessing", "guessing_leaderboard", {"guild_id": "all"}),
        ],
    },
]

PUBLIC_LINKS = [
    ("Home", "index", {}),
    ("Submissions", "index", {}),
    ("My Submissions", "my_submissions", {}),
    ("Servers", "servers", {}),
    ("Stats", "public_stats", {}),
    ("Guessing", "guessing_leaderboard", {}),
    ("Achievements", "achievements", {}),
    ("About", "about", {}),
    ("Invite Bot", "bot_invite", {}),
    ("Setup Guide", "setup_guide", {}),
]

CROSS_SERVER_LINKS = [
    ("All Submissions", "index", {"guild_id": "all"}),
    ("All Guessing", "guessing_leaderboard", {"guild_id": "all"}),
    ("Servers", "servers", {}),
    ("Stats", "public_stats", {"guild_id": "all"}),
]

PUBLIC_SIDEBAR_ENDPOINTS = {
    "index",
    "about",
    "bot_invite",
    "public_privacy_policy",
    "public_terms",
    "setup_guide",
    "servers",
    "server_profile",
    "public_stats",
    "guessing_leaderboard",
    "achievements",
    "account_login",
    "account_register",
    "account_home",
    "account_access_debug",
    "my_submissions",
    "user_profile",
    "report_submission",
}

SIDEBAR_BLOCKED_ENDPOINTS = {
    "admin_login",
    "admin_logout",
    "admin_oauth_start",
    "admin_oauth_callback",
    "account_oauth_start",
    "account_oauth_callback",
}

ADMIN_KEY_PUBLIC_ENDPOINTS = {
    "index",
    "audit_log",
    "my_submissions",
    "user_profile",
}


def admin_sidebar_sections(has_admin_role, admin_url):
    rendered_sections = []
    for section in ADMIN_SECTIONS:
        if not has_admin_role(section["required_role"]):
            continue
        rendered_links = []
        section_active = False
        for label, endpoint, values in section["links"]:
            try:
                active = request.endpoint == endpoint
                section_active = section_active or active
                rendered_links.append({
                    "label": label,
                    "url": admin_url(endpoint, **values),
                    "active": active,
                })
            except Exception:
                continue
        if rendered_links:
            rendered_sections.append({
                "label": section["label"],
                "active": section_active,
                "links": rendered_links,
            })
    return rendered_sections


def public_sidebar_sections():
    rendered_links = []
    section_active = False
    for label, endpoint, values in PUBLIC_LINKS:
        try:
            active = request.endpoint == endpoint
            section_active = section_active or active
            rendered_links.append({
                "label": label,
                "url": url_for(endpoint, **values),
                "active": active,
            })
        except Exception:
            continue
    cross_links = []
    cross_active = False
    for label, endpoint, values in CROSS_SERVER_LINKS:
        try:
            active = request.endpoint == endpoint and request.args.get("guild_id", "all") == "all"
            cross_active = cross_active or active
            cross_links.append({
                "label": label,
                "url": url_for(endpoint, **values),
                "active": active,
            })
        except Exception:
            continue
    sections = [{
        "label": "User",
        "active": section_active,
        "links": rendered_links,
    }]
    if cross_links:
        sections.append({
            "label": "Cross Server",
            "active": cross_active,
            "links": cross_links,
        })
    return sections


def sidebar_sections(is_admin_logged_in, has_admin_role, admin_url):
    if is_admin_logged_in():
        return admin_sidebar_sections(has_admin_role, admin_url)
    return public_sidebar_sections()


def should_render_public_sidebar():
    return request.endpoint in PUBLIC_SIDEBAR_ENDPOINTS


def admin_sidebar_links(has_admin_role, admin_url):
    return [
        link
        for section in admin_sidebar_sections(has_admin_role, admin_url)
        for link in section["links"]
    ]


def flatten_sidebar_links(sections):
    seen = set()
    flattened = []
    for section in sections:
        for link in section["links"]:
            key = (link["label"], link["url"])
            if key in seen:
                continue
            seen.add(key)
            flattened.append(link)
    return flattened

def should_render_admin_sidebar(is_admin_logged_in, admin_key):
    if request.endpoint in SIDEBAR_BLOCKED_ENDPOINTS:
        return False
    if not is_admin_logged_in():
        return should_render_public_sidebar()
    if request.path == "/admin" or request.path.startswith("/admin/"):
        return True
    if request.endpoint in ADMIN_KEY_PUBLIC_ENDPOINTS and request.args.get("key") == admin_key:
        return True
    return should_render_public_sidebar()



def is_native_app_view():
    if request.args.get("sdac_app") == "1":
        session["sdac_native_app"] = "1"
        return True
    referrer = (request.referrer or "").strip().lower()
    if referrer.startswith("capacitor://localhost") or referrer.startswith("ionic://localhost"):
        session["sdac_native_app"] = "1"
        return True
    return session.get("sdac_native_app") == "1"

def admin_sidebar_html(
    *,
    admin_key,
    role_labels,
    has_admin_role,
    is_admin_logged_in,
    is_account_logged_in,
    current_admin_role,
    current_admin_username,
    is_bot_owner_username,
    current_account_username,
    normalize_role,
    load_config,
    sidebar_server_options,
    admin_url,
):
    account_url = (
        url_for("account_home", key=admin_key)
        if is_account_logged_in()
        else url_for("account_login", next=request.full_path)
    )
    account_label = "My Account" if is_account_logged_in() else "Account Login"
    if is_admin_logged_in():
        role = role_labels.get(current_admin_role(), current_admin_role().title())
        username = current_admin_username()
        brand = "Sana-Chan Admin"
    elif is_account_logged_in():
        account_role = "bot_owner" if is_bot_owner_username(current_account_username()) else normalize_role(session.get("sdac_account_role"))
        role = role_labels.get(account_role, "User")
        username = current_account_username()
        brand = "Sana-Chan"
    else:
        role = "Public"
        username = "Guest"
        brand = "Sana-Chan"

    home_url = admin_url("admin_staff_home") if is_admin_logged_in() else url_for("index")
    home_active = " active" if request.endpoint in {"admin_staff_home", "index"} else ""
    nav_sections = []
    for section in sidebar_sections(is_admin_logged_in, has_admin_role, admin_url):
        section_links = []
        for link in section["links"]:
            if link["label"] == "Home":
                continue
            active_class = " active" if link["active"] else ""
            section_links.append(
                f'<a class="sdac-sidebar-link{active_class}" '
                f'href="{html.escape(link["url"], quote=True)}">'
                f'{html.escape(link["label"])}</a>'
            )
        if section_links:
            active_class = " active" if section.get("active") else ""
            open_attr = " open" if section.get("active") else ""
            nav_sections.append(
                f'<details class="sdac-sidebar-section sdac-sidebar-main-section{active_class}"{open_attr}>'
                f'<summary class="sdac-sidebar-section-title">'
                f'<span>{html.escape(section["label"])}</span>'
                '<span class="sdac-sidebar-section-caret" aria-hidden="true">+</span>'
                '</summary>'
                '<div class="sdac-sidebar-section-links">'
                + "".join(section_links)
                + "</div></details>"
            )
    navigation = '<nav class="sdac-sidebar-nav">' + "".join(nav_sections) + "</nav>"

    switcher = ""
    access_warning = ""
    if is_account_logged_in() or is_admin_logged_in():
        config_data = load_config()
        option_rows = sidebar_server_options(config_data)
        options = ['<option value="all">All Allowed Servers</option>']
        if not option_rows:
            access_warning = '<div class="sdac-sidebar-warning">No linked servers. Refresh Discord servers or ask a Bot Owner to assign access.</div>'
        current_guild = request.args.get("guild_id") or session.get("sdac_guild_id", "all") or "all"
        for guild in option_rows:
            selected = " selected" if current_guild == str(guild["id"]) else ""
            options.append(f'<option value="{html.escape(str(guild["id"]), quote=True)}"{selected}>{html.escape(guild["name"])}</option>')
        hidden_fields = []
        for key, value in request.args.items():
            if key in {"guild_id", "key"}:
                continue
            hidden_fields.append(
                '<input type="hidden" name="' + html.escape(key, quote=True) + '" value="' + html.escape(value, quote=True) + '">'
            )
        if is_admin_logged_in():
            hidden_fields.append('<input type="hidden" name="key" value="' + html.escape(admin_key, quote=True) + '">')
        switcher = (
            '<form class="sdac-server-switcher" method="get" action="' + html.escape(request.path or url_for("index"), quote=True) + '">'
            + ''.join(hidden_fields) +
            '<label>Server</label><select name="guild_id" onchange="this.form.submit()">' + ''.join(options) + '</select>'
            '<button type="submit">Open</button></form>'
        )
    return f"""
<div class="sdac-sidebar-controls">
    <button class="sdac-sidebar-toggle" type="button" aria-controls="sdac-sidebar" aria-expanded="true" onclick="sdacToggleSidebar()">Menu</button>
    <a class="sdac-sidebar-home{home_active}" href="{html.escape(home_url, quote=True)}">Home</a>
</div>
<aside class="sdac-sidebar" id="sdac-sidebar">
    <div class="sdac-sidebar-scroll">
        <div class="sdac-sidebar-brand">{html.escape(brand)}</div>
        <div class="sdac-sidebar-user">{html.escape(username)}<br><span>{html.escape(role)}</span></div>
        {switcher}
        {access_warning}
        {navigation}
        <div class="sdac-sidebar-footer">
            <a class="sdac-sidebar-invite" href="{html.escape(url_for("bot_invite"), quote=True)}">Invite Bot</a>
            <a class="sdac-sidebar-link" href="{html.escape(account_url, quote=True)}">{html.escape(account_label)}</a>
            {('<a class="sdac-sidebar-link" href="' + html.escape(url_for("account_access_debug", next=request.full_path), quote=True) + '">Access Debug</a>') if is_account_logged_in() else ''}
            {('<a class="sdac-sidebar-link" href="' + html.escape(url_for("account_refresh_discord", next=request.full_path), quote=True) + '">Refresh Discord Servers</a>') if is_account_logged_in() else ''}
            {('<a class="sdac-sidebar-link" href="' + html.escape(url_for("account_server", next=request.full_path), quote=True) + '">Change Server</a>') if is_account_logged_in() else ''}
            {('<div class="sdac-sidebar-warning">Use the app Login with Discord button above the dashboard.</div>' if is_native_app_view() else '<a class="sdac-sidebar-link" href="' + html.escape(url_for("account_oauth_start", next=request.full_path), quote=True) + '">Login with Discord</a>') if not is_account_logged_in() else ''}
            {('<a class="sdac-sidebar-link" href="' + html.escape(url_for("account_register"), quote=True) + '">Create Account</a>') if not is_account_logged_in() else ''}
            {('<a class="sdac-sidebar-link" href="' + html.escape(admin_url("admin_logout"), quote=True) + '">Logout</a>') if is_admin_logged_in() else ''}
            {('<a class="sdac-sidebar-link" href="' + html.escape(url_for("account_logout"), quote=True) + '">Logout</a>') if is_account_logged_in() and not is_admin_logged_in() else ''}
        </div>
    </div>
</aside><script>
(function () {{
    try {{ localStorage.removeItem("sdacSidebarCollapsed"); }} catch (error) {{}}
    window.sdacToggleSidebar = function () {{
        var isMobile = window.matchMedia("(max-width: 900px)").matches;
        if (isMobile) {{
            document.body.classList.toggle("sdac-sidebar-open");
            return;
        }}
        document.body.classList.toggle("sdac-sidebar-collapsed");
    }};
}}());
</script>
"""



