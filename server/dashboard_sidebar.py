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
            ("Events", "community_events", {}),
            ("Meetups", "community_meetups", {}),
            ("Quotes", "community_quotes", {}),
            ("My Submissions", "my_submissions", {}),
            ("Notifications", "notification_inbox", {}),
            ("Support", "support_center", {}),
            ("Appeals", "moderation_appeals", {}),
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
            ("Command Center", "admin_command_center", {}),
            ("Notifications", "admin_notification_center", {}),
            ("Moderator Workspace", "admin_moderator_workspace", {}),
            ("Reaction Roles", "reaction_roles.manage", {}),
            ("Website Editor", "site_editor.manage", {}),
            ("Case Management", "admin_case_management", {}),
            ("Review Queue", "admin_moderation", {}),
            ("Events / Meetups", "admin_community_submissions", {}),
            ("Quote Moderation", "admin_quote_submissions", {}),
            ("Removal Reasons", "admin_removal_reasons", {}),
            ("Users", "admin_users", {}),
            ("Polls", "admin_polls", {}),
            ("Audit", "audit_log", {}),
            ("Anime Activities", "admin_anime_activities", {}),
            ("Metrics", "admin_overview", {}),
            ("Game Library", "admin_game_library", {}),
        ],
    },
    {
        "label": "Server Owner",
        "required_role": "owner",
        "links": [
            ("Setup Wizard", "admin_setup_wizard", {}),
            ("Launch Scores", "admin_launch_scores", {}),
            ("Discord Panels", "admin_discord_panels", {}),
            ("Setup Checklist", "admin_setup_checklist", {}),
            ("Categories", "admin_category_manager", {}),
            ("Permissions", "admin_permission_health", {}),
            ("Settings", "admin_settings", {}),
            ("Server Health", "admin_server_health_cards", {}),
            ("Media", "admin_media_cleanup", {}),
            ("Seasons", "admin_seasons", {}),
            ("Theme", "admin_theme", {}),
            ("Theme Presets", "admin_theme_presets", {}),
            ("Layout", "admin_layout", {}),
            ("Training Mode", "admin_training_mode", {}),
            ("Onboarding", "admin_onboarding", {}),
            ("Privacy", "admin_privacy", {}),
            ("Owner Portal", "admin_owner_portal", {}),
        ],
    },
    {
        "label": "Full Site Access",
        "required_role": "bot_owner",
        "links": [
            ("Release Center", "admin_release_center", {}),
            ("Operations Dashboard", "admin_operations_dashboard", {}),
            ("Recovery Validation", "admin_recovery_validation", {}),
            ("Go Live Control", "admin_go_live_control_room", {}),
            ("OAuth Diagnostics", "admin_oauth_diagnostics", {}),
            ("Release Notes Preview", "admin_release_notes_preview", {}),
            ("Self Tests", "admin_self_tests", {}),
            ("Command Audit", "admin_command_cleanup_audit", {}),
            ("App Store Readiness", "admin_app_store_readiness", {}),
            ("Mobile Pass", "admin_mobile_dashboard_pass", {}),
            ("Empty States", "admin_empty_states", {}),
            ("Permission Simulator", "admin_permission_simulator", {}),
            ("Install Success", "admin_install_success", {}),
            ("Activity Digest", "admin_activity_digest", {}),
            ("Command Center", "admin_command_center", {}),
            ("Notifications", "admin_notification_center", {}),
            ("Post-Update Wizard", "admin_post_update_wizard", {}),
            ("Undo Center", "admin_undo_center", {}),
            ("Global Control", "admin_global_control", {}),
            ("Maintenance Mode", "admin_maintenance_mode", {}),
            ("Maintenance Planner", "admin_maintenance_planner", {}),
            ("Config History", "admin_config_history", {}),
            ("Maintenance", "admin_maintenance", {}),
            ("Optimization", "admin_optimization", {}),
            ("Releases", "admin_releases", {}),
            ("Release Checklist", "admin_release_checklist", {}),
            ("Go Live Checklist", "admin_go_live_checklist", {}),
            ("Production", "admin_production_health", {}),
            ("Install Doctor", "admin_install_doctor", {}),
            ("UI Health", "admin_ui_health", {}),
            ("UI Preview", "admin_ui_preview", {}),
            ("Report A Problem", "admin_report_problem", {}),
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


ADMIN_LINK_GROUPS = {
    "User": [
        ("Workspace", ["Staff Home", "Submissions", "Events", "Meetups", "Quotes"]),
        ("My Account", ["My Submissions", "Notifications", "Support", "Appeals"]),
        ("Community", ["Guessing", "Servers", "Stats", "Achievements"]),
    ],
    "Moderator": [
        ("Moderation", ["Moderator Workspace", "Case Management", "Review Queue", "Removal Reasons", "Users"]),
        ("Community", ["Events / Meetups", "Quote Moderation", "Polls"]),
        ("Server Tools", ["Command Center", "Notifications", "Reaction Roles", "Website Editor", "Audit", "Metrics"]),
        ("Anime & Games", ["Anime Activities", "Game Library"]),
    ],
    "Server Owner": [
        ("Setup & Access", ["Setup Wizard", "Setup Checklist", "Categories", "Permissions", "Settings", "Discord Panels"]),
        ("Appearance", ["Theme", "Theme Presets", "Layout"]),
        ("Operations", ["Launch Scores", "Server Health", "Media", "Seasons"]),
        ("Safety & Onboarding", ["Training Mode", "Onboarding", "Privacy", "Owner Portal"]),
    ],
    "Full Site Access": [
        ("Releases & Launch", ["Release Center", "Release Notes Preview", "Releases", "Release Checklist", "Go Live Control", "Go Live Checklist", "App Store Readiness", "Mobile Pass", "Install Success", "Post-Update Wizard"]),
        ("Operations & Recovery", ["Operations Dashboard", "Recovery Validation", "Undo Center", "Maintenance Mode", "Maintenance Planner", "Maintenance", "Optimization", "Production", "Install Doctor", "Jobs"]),
        ("Diagnostics & Quality", ["OAuth Diagnostics", "Self Tests", "Command Audit", "Empty States", "Permission Simulator", "UI Health", "UI Preview", "Report A Problem"]),
        ("Site Management", ["Global Control", "Notifications", "Command Center", "Activity Digest", "Config History", "Server Switcher", "Preview As", "Approvals"]),
        ("Reports & Analytics", ["Analytics", "Monthly Report", "All Submissions", "All Guessing"]),
    ],
}

PUBLIC_LINK_GROUPS = [
    ("Browse", ["Home", "Submissions", "Events", "Meetups", "Quotes", "Servers"]),
    ("My Account", ["My Submissions", "Notifications", "Support", "Appeals"]),
    ("Community & Help", ["Guessing", "Stats", "Achievements", "API Docs", "Status", "About", "Invite Bot", "Setup Guide"]),
]

CROSS_LINK_GROUPS = [
    ("Across Servers", ["All Submissions", "All Guessing", "Servers", "Stats"]),
]


def group_sidebar_links(links, definitions):
    """Group links for the compact nested sidebar while retaining flat links for callers."""
    remaining = list(links)
    groups = []
    for label, link_labels in definitions:
        group_links = [link for link in remaining if link["label"] in link_labels]
        remaining = [link for link in remaining if link["label"] not in link_labels]
        if group_links:
            groups.append({
                "label": label,
                "active": any(link["active"] for link in group_links),
                "links": group_links,
            })
    if remaining:
        groups.append({
            "label": "More",
            "active": any(link["active"] for link in remaining),
            "links": remaining,
        })
    return groups

PUBLIC_LINKS = [
    ("Home", "index", {}),
    ("Submissions", "index", {}),
    ("Events", "community_events", {}),
    ("Meetups", "community_meetups", {}),
    ("Quotes", "community_quotes", {}),
    ("My Submissions", "my_submissions", {}),
    ("Notifications", "notification_inbox", {}),
    ("Support", "support_center", {}),
    ("API Docs", "public_api_docs", {}),
    ("Status", "public_service_status", {}),
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
    "notification_inbox",
    "support_center",
    "moderation_appeals",
    "public_api_docs",
    "public_service_status",
    "community_events",
    "community_meetups",
    "community_quotes",
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
    visible_urls = set()
    for section in ADMIN_SECTIONS:
        if not has_admin_role(section["required_role"]):
            continue
        rendered_links = []
        section_active = False
        for label, endpoint, values in section["links"]:
            try:
                active = request.endpoint == endpoint
                link_url = admin_url(endpoint, **values)
                if link_url in visible_urls:
                    continue
                section_active = section_active or active
                rendered_links.append({
                    "label": label,
                    "url": link_url,
                    "active": active,
                })
                visible_urls.add(link_url)
            except Exception:
                continue
        if rendered_links:
            rendered_sections.append({
                "label": section["label"],
                "active": section_active,
                "links": rendered_links,
                "groups": group_sidebar_links(
                    rendered_links,
                    ADMIN_LINK_GROUPS.get(section["label"], []),
                ),
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
        "groups": group_sidebar_links(rendered_links, PUBLIC_LINK_GROUPS),
    }]
    if cross_links:
        sections.append({
            "label": "Cross Server",
            "active": cross_active,
            "links": cross_links,
            "groups": group_sidebar_links(cross_links, CROSS_LINK_GROUPS),
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
    if admin_key and request.endpoint in ADMIN_KEY_PUBLIC_ENDPOINTS and request.args.get("key") == admin_key:
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
    health_badge=None,
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
        url_for("account_home")
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
        def render_links(links):
            output = []
            for link in links:
                if link["label"] == "Home":
                    continue
                active_class = " active" if link["active"] else ""
                output.append(
                    f'<a class="sdac-sidebar-link{active_class}" '
                    f'href="{html.escape(link["url"], quote=True)}">'
                    f'{html.escape(link["label"])}</a>'
                )
            return "".join(output)

        section_links = []
        for group in section.get("groups", []):
            group_links = render_links(group["links"])
            if not group_links:
                continue
            group_active = " active" if group.get("active") else ""
            group_open = " open" if group.get("active") else ""
            section_links.append(
                f'<details class="sdac-sidebar-subsection{group_active}"{group_open}>'
                f'<summary class="sdac-sidebar-subsection-title">'
                f'<span>{html.escape(group["label"])}</span>'
                '<span class="sdac-sidebar-subsection-caret" aria-hidden="true">+</span>'
                '</summary>'
                '<div class="sdac-sidebar-subsection-links">'
                + group_links
                + '</div></details>'
            )
        if not section_links:
            section_links.append(render_links(section["links"]))
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
    navigation = '<nav class="sdac-sidebar-nav" id="sdac-sidebar-nav" aria-label="Site navigation">' + "".join(nav_sections) + "</nav>"

    switcher = ""
    access_warning = ""
    if is_account_logged_in() or is_admin_logged_in():
        config_data = load_config()
        option_rows = sidebar_server_options(config_data)
        options = []
        if not option_rows:
            access_warning = '<div class="sdac-sidebar-warning">No linked servers. Refresh Discord servers or ask a Bot Owner to assign access.</div>'
        requested_guild = str(request.args.get("guild_id") or "").strip()
        stored_guild = str(session.get("sdac_guild_id", "") or "").strip()
        valid_option_ids = {str(guild["id"]) for guild in option_rows}
        current_guild = "all"
        if requested_guild == "all":
            current_guild = "all"
        elif requested_guild in valid_option_ids:
            current_guild = requested_guild
        elif stored_guild in valid_option_ids:
            current_guild = stored_guild
        options = [f'<option value="all"{(" selected" if current_guild == "all" else "")}>All Allowed Servers</option>']
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
        if is_admin_logged_in() and admin_key:
            hidden_fields.append('<input type="hidden" name="key" value="' + html.escape(admin_key, quote=True) + '">')
        switcher = (
            '<form class="sdac-server-switcher" method="get" action="' + html.escape(request.path or url_for("index"), quote=True) + '">'
            + ''.join(hidden_fields) +
            '<label>Server</label><select name="guild_id" onchange="this.form.submit()">' + ''.join(options) + '</select>'
            '<button type="submit">Open</button></form>'
        )
    badge_html = ""
    if health_badge:
        badge_class = "ok" if health_badge.get("state") == "Healthy" else "warn" if health_badge.get("state") != "OAuth Issue" else "bad"
        badge_html = (
            '<a class="sdac-sidebar-health ' + badge_class + '" href="' + html.escape(health_badge.get("url", "#"), quote=True) + '">'
            + html.escape(health_badge.get("state", "Health")) + '</a>'
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
        {badge_html}
        {switcher}
        {access_warning}
        <div class="sdac-sidebar-search-wrap">
            <label for="sdac-sidebar-search">Find a page</label>
            <input id="sdac-sidebar-search" type="search" placeholder="Search dashboard pages" autocomplete="off" aria-controls="sdac-sidebar-nav">
            <span id="sdac-sidebar-search-status" class="sdac-sidebar-search-status" aria-live="polite"></span>
        </div>
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
<style>
.sdac-sidebar-search-wrap {{ margin: 10px 8px 12px; }}
.sdac-sidebar-search-wrap label {{ display: block; font-size: .75rem; font-weight: 700; margin-bottom: 5px; }}
.sdac-sidebar-search-wrap input {{ box-sizing: border-box; width: 100%; min-height: 38px; border: 1px solid var(--sdac-border, #34415c); border-radius: 8px; padding: 8px 10px; background: var(--sdac-surface, #111827); color: var(--sdac-text, #f8fafc); }}
.sdac-sidebar-search-status {{ display: block; font-size: .72rem; min-height: 1em; margin-top: 3px; color: var(--sdac-muted, #94a3b8); }}
</style>
</aside><script>
(function () {{
    try {{ localStorage.removeItem("sdacSidebarCollapsed"); }} catch (error) {{}}
    var search = document.getElementById("sdac-sidebar-search");
    var nav = document.getElementById("sdac-sidebar-nav");
    var status = document.getElementById("sdac-sidebar-search-status");
    if (search && nav) {{
        search.addEventListener("input", function () {{
            var query = search.value.trim().toLocaleLowerCase();
            var visibleCount = 0;
            nav.querySelectorAll(".sdac-sidebar-link").forEach(function (link) {{
                var visible = !query || link.textContent.toLocaleLowerCase().includes(query);
                link.hidden = !visible;
                if (visible) visibleCount += 1;
            }});
            nav.querySelectorAll(".sdac-sidebar-subsection").forEach(function (group) {{
                var hasVisible = !!group.querySelector(".sdac-sidebar-link:not([hidden])");
                group.hidden = !hasVisible;
                if (query && hasVisible) group.open = true;
            }});
            nav.querySelectorAll(".sdac-sidebar-main-section").forEach(function (section) {{
                var hasVisible = !!section.querySelector(".sdac-sidebar-link:not([hidden])");
                section.hidden = !hasVisible;
                if (query && hasVisible) section.open = true;
            }});
            if (status) status.textContent = query ? (visibleCount + (visibleCount === 1 ? " page found" : " pages found")) : "";
        }});
    }}
    window.sdacToggleSidebar = function () {{
        var isMobile = window.matchMedia("(max-width: 900px)").matches;
        if (isMobile) {{
            document.body.classList.toggle("sdac-sidebar-open");
        }} else {{
            document.body.classList.toggle("sdac-sidebar-collapsed");
        }}
        var button = document.querySelector(".sdac-sidebar-toggle");
        if (button) button.setAttribute("aria-expanded", String(isMobile
            ? document.body.classList.contains("sdac-sidebar-open")
            : !document.body.classList.contains("sdac-sidebar-collapsed")));
    }};
}}());
</script>
"""



