"""Static HTML assets injected into rendered dashboard pages."""

PWA_HEAD_HTML = """
<link rel="manifest" href="/manifest.webmanifest">
<meta name="application-name" content="SDAC">
<meta name="apple-mobile-web-app-title" content="SDAC">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#4f46e5">
<link rel="icon" href="/app-icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/app-icon.svg">
"""

PWA_INSTALL_HTML = """
<style id="sdac-pwa-style">
.sdac-install-app-button {
    align-items: center;
    background: linear-gradient(90deg, var(--sdac-primary, #4f46e5), var(--sdac-secondary, #06b6d4));
    border: 0;
    border-radius: 8px;
    bottom: 16px;
    box-shadow: 0 16px 42px rgba(2, 6, 23, .34);
    color: #fff;
    cursor: pointer;
    display: none;
    font-weight: 850;
    gap: 8px;
    justify-content: center;
    line-height: 1;
    margin: 0;
    max-width: calc(100vw - 32px);
    min-height: 42px;
    padding: 11px 14px;
    position: fixed;
    right: 16px;
    width: auto;
    z-index: 1003;
}
.sdac-install-app-button.is-visible { display: inline-flex; }
@media (max-width: 56rem) {
    .sdac-install-app-button { bottom: 12px; right: 12px; }
}
</style>
<button class="sdac-install-app-button" id="sdac-install-app-button" type="button">Install App</button>
<script id="sdac-pwa-script">
(() => {
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/sw.js').catch(() => {});
        });
    }
    let deferredInstallPrompt = null;
    const installButton = document.getElementById('sdac-install-app-button');
    if (!installButton) return;
    window.addEventListener('beforeinstallprompt', (event) => {
        event.preventDefault();
        deferredInstallPrompt = event;
        installButton.classList.add('is-visible');
    });
    installButton.addEventListener('click', async () => {
        if (!deferredInstallPrompt) return;
        installButton.classList.remove('is-visible');
        deferredInstallPrompt.prompt();
        try { await deferredInstallPrompt.userChoice; } catch (error) {}
        deferredInstallPrompt = null;
    });
    window.addEventListener('appinstalled', () => {
        installButton.classList.remove('is-visible');
        deferredInstallPrompt = null;
    });
})();
</script>
"""
SIDEBAR_STYLE = """
<style id="sdac-sidebar-style">
:root {
    --sdac-primary: #4f46e5;
    --sdac-secondary: #06b6d4;
    --sdac-accent: #f59e0b;
    --sdac-bg: #0f172a;
    --sdac-surface: #111827;
    --sdac-sidebar-bg: #0b1220;
    --sdac-text: #f8fafc;
    --sdac-muted: #94a3b8;
    --sdac-border: rgba(148, 163, 184, 0.24);
    --sdac-content-width: min(96%, 76rem);
    --sdac-sidebar-width: clamp(13.75rem, 17vw, 17.5rem);
    --sdac-card-radius: 0.5rem;
    --sdac-panel-padding: clamp(0.75rem, 1.4vw, 1.15rem);
    --sdac-grid-min: min(100%, 12rem);
    --sdac-layout-gap: clamp(0.6rem, 1.2vw, 1rem);
    --sdac-bg-position: center;
    --sdac-sidebar-gap: clamp(0.75rem, 1.5vw, 1.5rem);
    --sdac-sidebar-toggle-left: clamp(0.6rem, 1.1vw, 1rem);
    --sdac-collapsed-sidebar-gutter: clamp(4.5rem, 7vw, 7rem);
}
html { min-height: 100%; }
body.sdac-theme {
    background-color: var(--sdac-bg) !important;
    color: var(--sdac-text) !important;
    min-height: 100dvh;
    overflow-x: hidden;
}
body.sdac-theme::before {
    content: "";
    position: fixed;
    inset: 0;
    background-image: var(--sdac-theme-image, linear-gradient(135deg, rgba(79,70,229,.24), rgba(6,182,212,.14) 45%, rgba(245,158,11,.10)));
    background-size: cover;
    background-position: var(--sdac-bg-position, center);
    opacity: var(--sdac-theme-image-opacity, .18);
    pointer-events: none;
    z-index: -1;
}
body.sdac-has-sidebar {
    box-sizing: border-box;
    padding-left: calc(var(--sdac-sidebar-width) + var(--sdac-sidebar-gap)) !important;
    transition: padding-left .18s ease;
}
body.sdac-has-sidebar.sdac-sidebar-collapsed { padding-left: var(--sdac-collapsed-sidebar-gutter) !important; }
body.sdac-has-sidebar main {
    box-sizing: border-box !important;
    margin-left: auto !important;
    margin-right: auto !important;
    max-width: var(--sdac-content-width) !important;
    min-width: 0 !important;
    width: min(100%, var(--sdac-content-width)) !important;
}
body.sdac-has-sidebar h1, body.sdac-has-sidebar h2 { text-align: left !important; }
body.sdac-has-sidebar main, body.sdac-has-sidebar main * { box-sizing: border-box; }
body.sdac-has-sidebar a { color: var(--sdac-secondary) !important; }
body.sdac-has-sidebar .panel, body.sdac-has-sidebar .post, body.sdac-has-sidebar .audit-row,
body.sdac-has-sidebar .section, body.sdac-has-sidebar table, body.sdac-has-sidebar .notice,
.sdac-dashboard-card, .sdac-dashboard-panel {
    background: color-mix(in srgb, var(--sdac-surface) 88%, transparent) !important;
    border-color: var(--sdac-border) !important;
    border-radius: var(--sdac-card-radius) !important;
    box-shadow: 0 18px 48px rgba(2, 6, 23, .24);
}
.sdac-sidebar-toggle {
    appearance: none !important;
    align-items: center !important;
    background: linear-gradient(90deg, var(--sdac-primary), var(--sdac-secondary)) !important;
    border: 1px solid var(--sdac-border) !important;
    border-radius: 8px !important;
    color: #fff !important;
    cursor: pointer !important;
    display: inline-flex !important;
    font-weight: 850 !important;
    justify-content: center !important;
    left: var(--sdac-sidebar-toggle-left) !important;
    line-height: 1 !important;
    margin: 0 !important;
    min-height: 36px !important;
    padding: 8px 12px !important;
    position: fixed !important;
    text-align: center !important;
    top: 14px !important;
    transition: left .18s ease, transform .18s ease;
    width: auto !important;
    z-index: 1002 !important;
}
body.sdac-menu-page-left .sdac-sidebar-toggle,
body.sdac-menu-viewport-left .sdac-sidebar-toggle,
body.sdac-sidebar-collapsed .sdac-sidebar-toggle { left: 16px !important; }
.sdac-sidebar {
    background: linear-gradient(180deg, var(--sdac-sidebar-bg), color-mix(in srgb, var(--sdac-sidebar-bg) 88%, #020617));
    box-shadow: 12px 0 34px rgba(2, 6, 23, 0.34);
    box-sizing: border-box;
    color: var(--sdac-text);
    display: flex;
    flex-direction: column;
    gap: 0;
    height: 100dvh;
    inset: 0 auto 0 0;
    max-width: calc(100vw - clamp(1rem, 3vw, 1.5rem));
    overflow: hidden;
    padding: clamp(3.25rem, 7dvh, 4rem) clamp(0.75rem, 1.6vw, 1rem) clamp(0.75rem, 1.6vw, 1rem);
    position: fixed;
    transform: translateX(0);
    transition: transform .18s ease;
    width: min(var(--sdac-sidebar-width), 82vw);
    z-index: 1001;
}
body.sdac-sidebar-collapsed .sdac-sidebar { transform: translateX(-105%); }
.sdac-sidebar nav {
    display: flex !important;
    flex: 1 1 auto;
    flex-direction: column !important;
    flex-wrap: nowrap !important;
    gap: 0 !important;
    justify-content: flex-start !important;
    margin: 0 !important;
    min-height: 0;
    overflow-x: hidden;
    overflow-y: auto;
    padding-right: 4px;
    text-align: left !important;
}
.sdac-sidebar nav::-webkit-scrollbar { width: 0.5rem; }
.sdac-sidebar nav::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, .35); border-radius: 999px; }
.sdac-sidebar-brand { flex: 0 0 auto; font-size: clamp(1.05rem, 1.4vw, 1.25rem); font-weight: 900; margin-bottom: 0.625rem; }
.sdac-sidebar-user { color: var(--sdac-muted); flex: 0 0 auto; font-size: clamp(0.82rem, 1vw, 0.9rem); line-height: 1.35; margin-bottom: clamp(0.75rem, 1.4vw, 1.125rem); }
.sdac-sidebar-user span { color: var(--sdac-secondary); }
.sdac-sidebar-warning { border: 1px solid #f59e0b; border-radius: 8px; color: #fde68a; flex: 0 0 auto; font-size: .82rem; line-height: 1.35; margin: 0 0 14px; padding: 9px 10px; }
.sdac-server-switcher { align-items: stretch !important; border: 1px solid var(--sdac-border); border-radius: 8px; box-sizing: border-box !important; display: grid !important; flex: 0 0 auto; gap: 6px; grid-template-columns: minmax(0, 1fr); inline-size: 100% !important; margin: 0 0 14px !important; max-inline-size: 100% !important; max-width: 100% !important; min-inline-size: 0 !important; min-width: 0 !important; overflow: hidden; padding: 10px !important; width: 100% !important; }
.sdac-server-switcher label { box-sizing: border-box !important; color: var(--sdac-muted); display: block !important; font-size: .72rem; font-weight: 800; margin: 0 !important; max-width: 100%; min-width: 0; overflow: hidden; text-overflow: ellipsis; text-transform: uppercase; white-space: nowrap; }
.sdac-sidebar .sdac-server-switcher select, .sdac-sidebar .sdac-server-switcher button { align-self: stretch !important; box-sizing: border-box !important; display: block !important; font-size: .86rem !important; inline-size: 100% !important; line-height: 1.2 !important; margin: 0 !important; max-inline-size: 100% !important; max-width: 100% !important; min-inline-size: 0 !important; min-width: 0 !important; overflow: hidden !important; padding: 8px 10px !important; text-overflow: ellipsis; white-space: nowrap; width: 100% !important; }
.sdac-sidebar-section { border: 1px solid var(--sdac-border); border-radius: 8px; flex: 0 0 auto; margin: 8px 0; overflow: hidden; }
.sdac-sidebar-section summary { color: var(--sdac-text); cursor: pointer; font-size: 0.78rem; font-weight: 850; letter-spacing: 0; list-style: none; padding: 10px 11px; text-transform: uppercase; }
.sdac-sidebar-section summary::-webkit-details-marker { display: none; }
.sdac-sidebar-section summary::after { content: "+"; float: right; font-size: 1rem; line-height: 0.85; }
.sdac-sidebar-section[open] summary::after { content: "-"; }
.sdac-sidebar-section[open] summary { background: color-mix(in srgb, var(--sdac-primary) 20%, transparent); }
.sdac-sidebar-section-links { padding: 4px 6px 8px; }
.sdac-sidebar-link { border-radius: 7px; color: var(--sdac-text) !important; display: block; font-weight: 650; margin: 2px 0; padding: 9px 11px; text-decoration: none; }
.sdac-sidebar-link:hover, .sdac-sidebar-link.active { color: #fff !important; background: linear-gradient(90deg, var(--sdac-primary), var(--sdac-secondary)); }
.sdac-sidebar-invite { align-items: center; background: linear-gradient(90deg, var(--sdac-primary), var(--sdac-secondary)); border-radius: 8px; color: #fff !important; display: inline-flex; font-weight: 850; justify-content: center; margin: 0 0 12px; min-height: 38px; padding: 9px 12px; text-decoration: none; width: 100%; }
.sdac-sidebar-invite:hover { color: #fff !important; filter: brightness(1.08); }
.sdac-sidebar-footer { border-top: 1px solid var(--sdac-border); flex: 0 0 auto; margin-top: 12px; max-height: 28dvh; overflow-y: auto; padding-top: 12px; }
body.sdac-has-sidebar > nav, body.sdac-has-sidebar main > nav:not(.pagination), body.sdac-has-sidebar .admin-nav { display: none !important; }
body.sdac-has-sidebar table { display: block; max-width: 100%; overflow-x: auto; width: 100%; }
body.sdac-has-sidebar form { max-width: 100%; }
body.sdac-has-sidebar input, body.sdac-has-sidebar select, body.sdac-has-sidebar textarea, body.sdac-has-sidebar button { max-width: 100%; min-width: 0; }
.sdac-dashboard-grid { display: grid; gap: var(--sdac-layout-gap); grid-template-columns: repeat(auto-fit, minmax(var(--sdac-grid-min), 1fr)); margin: clamp(0.75rem, 1.6vw, 1.25rem) 0; }
.sdac-dashboard-card { border: 1px solid var(--sdac-border); border-radius: var(--sdac-card-radius); padding: var(--sdac-panel-padding); }
.sdac-dashboard-card strong { display: block; font-size: clamp(1.35rem, 2.2vw, 1.8rem); line-height: 1.1; }
.sdac-dashboard-card span { color: var(--sdac-muted); display: block; font-size: .82rem; font-weight: 750; margin-top: 6px; text-transform: uppercase; }
.sdac-dashboard-panel { border: 1px solid var(--sdac-border); border-radius: var(--sdac-card-radius); margin: clamp(0.75rem, 1.4vw, 1.125rem) 0; padding: var(--sdac-panel-padding); }
.sdac-range-tabs { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.sdac-range-tabs a { border: 1px solid var(--sdac-border); border-radius: 7px; padding: 8px 10px; text-decoration: none; }
.sdac-range-tabs a.active { background: var(--sdac-primary); color: #fff !important; }
@media (max-width: 56rem) {
    body.sdac-has-sidebar,
    body.sdac-has-sidebar.sdac-sidebar-collapsed { padding-left: 0 !important; }
    body.sdac-has-sidebar main { padding-top: clamp(3rem, 8dvh, 3.75rem) !important; }
    .sdac-sidebar-toggle { left: clamp(0.65rem, 2.5vw, 0.85rem) !important; top: clamp(0.65rem, 2.5vw, 0.85rem) !important; }
    .sdac-sidebar { border-radius: 0 0.875rem 0.875rem 0; box-shadow: 1.125rem 0 2.5rem rgba(2, 6, 23, 0.48); transform: translateX(-105%); }
    body.sdac-sidebar-open .sdac-sidebar { transform: translateX(0); }
    body.sdac-sidebar-open .sdac-sidebar-toggle { left: clamp(0.65rem, 2.5vw, 0.85rem) !important; }
    body.sdac-sidebar-open.sdac-menu-viewport-left .sdac-sidebar-toggle { left: clamp(0.65rem, 2.5vw, 0.85rem) !important; }
}
</style>
"""
