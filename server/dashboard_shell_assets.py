"""Static HTML assets injected into rendered dashboard pages."""

PWA_HEAD_HTML = """
<link rel="manifest" href="/manifest.webmanifest">
<meta name="application-name" content="Sana-Chan">
<meta name="apple-mobile-web-app-title" content="Sana-Chan">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#030713">
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
    --sdac-primary: #8b5cf6;
    --sdac-secondary: #18d9ff;
    --sdac-accent: #b45cff;
    --sdac-success: #34d399;
    --sdac-danger: #fb7185;
    --sdac-bg: #030713;
    --sdac-surface: #080f20;
    --sdac-surface-strong: #11182b;
    --sdac-sidebar-bg: #050a17;
    --sdac-text: #f8fbff;
    --sdac-muted: #a6b0ca;
    --sdac-border: rgba(126, 151, 255, 0.24);
    --sdac-glow-cyan: rgba(24, 217, 255, 0.34);
    --sdac-glow-violet: rgba(139, 92, 246, 0.38);
    --sdac-content-width: min(96%, 76rem);
    --sdac-sidebar-width: clamp(13.75rem, 17vw, 17.5rem);
    --sdac-card-radius: 0.75rem;
    --sdac-panel-padding: clamp(0.75rem, 1.4vw, 1.15rem);
    --sdac-grid-min: min(100%, 12rem);
    --sdac-layout-gap: clamp(0.6rem, 1.2vw, 1rem);
    --sdac-bg-position: center;
    --sdac-sidebar-gap: clamp(0.75rem, 1.5vw, 1.5rem);
    --sdac-sidebar-toggle-left: clamp(0.6rem, 1.1vw, 1rem);
    --sdac-collapsed-sidebar-gutter: clamp(4.5rem, 7vw, 7rem);
}
html { max-width: 100%; min-height: 100%; overflow-x: hidden !important; width: 100%; }
body.sdac-theme {
    background-color: var(--sdac-bg) !important;
    background-image:
        radial-gradient(circle at 9% 8%, rgba(139, 92, 246, 0.24), transparent 24rem),
        radial-gradient(circle at 76% 10%, rgba(24, 217, 255, 0.12), transparent 28rem),
        radial-gradient(circle at 86% 80%, rgba(180, 92, 255, 0.13), transparent 24rem),
        linear-gradient(135deg, #030713 0%, #081126 48%, #050b18 100%) !important;
    color: var(--sdac-text) !important;
    max-width: 100%;
    min-height: 100dvh;
    overflow-x: hidden !important;
    position: relative;
    width: 100%;
}
body.sdac-theme::before {
    content: "";
    position: fixed;
    inset: 0;
    background-image: var(--sdac-theme-image, linear-gradient(135deg, rgba(139,92,246,.16), rgba(24,217,255,.10) 45%, rgba(180,92,255,.12)));
    background-size: cover;
    background-position: var(--sdac-bg-position, center);
    opacity: var(--sdac-theme-image-opacity, .16);
    pointer-events: none;
    z-index: -2;
}
body.sdac-theme::after {
    content: "";
    position: fixed;
    inset: 0;
    background-image:
        radial-gradient(circle, rgba(139, 92, 246, .42) 0 1.5px, transparent 1.8px),
        linear-gradient(135deg, transparent 0 72%, rgba(139, 92, 246, .16) 72.3%, transparent 74.5%),
        linear-gradient(145deg, transparent 0 78%, rgba(24, 217, 255, .12) 78.2%, transparent 80%);
    background-position: right 3rem top 2rem, left bottom, right bottom;
    background-repeat: repeat, no-repeat, no-repeat;
    background-size: 1.6rem 1.6rem, 38rem 18rem, 44rem 24rem;
    opacity: .18;
    pointer-events: none;
    z-index: -1;
}
body.sdac-has-sidebar {
    box-sizing: border-box;
    max-width: 100vw;
    overflow-x: hidden !important;
    padding-left: calc(var(--sdac-sidebar-width) + var(--sdac-sidebar-gap)) !important;
    transition: padding-left .18s ease;
    width: 100%;
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
    backdrop-filter: blur(16px) saturate(1.15);
    background: linear-gradient(180deg, rgba(17, 24, 43, .86), rgba(8, 15, 32, .92)) !important;
    border: 1px solid var(--sdac-border) !important;
    border-radius: var(--sdac-card-radius) !important;
    box-shadow: 0 24px 64px rgba(0, 0, 0, .44), 0 0 0 1px rgba(24, 217, 255, .05) inset, 0 0 34px rgba(139, 92, 246, .08);
}
.sdac-sidebar-controls {
    align-items: center !important;
    display: flex !important;
    gap: 8px !important;
    left: var(--sdac-sidebar-toggle-left) !important;
    position: fixed !important;
    top: 14px !important;
    z-index: 1002 !important;
}
body.sdac-menu-page-left .sdac-sidebar-controls,
body.sdac-menu-viewport-left .sdac-sidebar-controls,
body.sdac-sidebar-collapsed .sdac-sidebar-controls { left: 16px !important; }
.sdac-sidebar-toggle,
.sdac-sidebar-home {
    appearance: none !important;
    align-items: center !important;
    border: 1px solid var(--sdac-border) !important;
    border-radius: 8px !important;
    cursor: pointer !important;
    display: inline-flex !important;
    font-weight: 850 !important;
    justify-content: center !important;
    line-height: 1 !important;
    margin: 0 !important;
    min-height: 36px !important;
    padding: 8px 12px !important;
    text-align: center !important;
    text-decoration: none !important;
    width: auto !important;
}
.sdac-sidebar-toggle {
    background: linear-gradient(100deg, #7c5cff, #18d9ff) !important;
    box-shadow: 0 0 24px rgba(24, 217, 255, .30), 0 10px 28px rgba(124, 92, 255, .18);
    color: #fff !important;
}
.sdac-sidebar-home { background: color-mix(in srgb, var(--sdac-surface) 82%, transparent); color: var(--sdac-text) !important; }
.sdac-sidebar-home:hover, .sdac-sidebar-home.active { color: #fff !important; background: linear-gradient(90deg, var(--sdac-primary), var(--sdac-secondary)); }
.sdac-sidebar {
    backdrop-filter: blur(18px) saturate(1.12);
    background:
        linear-gradient(180deg, rgba(5, 10, 23, .96), rgba(8, 15, 32, .93)),
        radial-gradient(circle at 45% 4%, rgba(139, 92, 246, .24), transparent 14rem);
    border-right: 1px solid rgba(126, 151, 255, .18);
    box-shadow: 18px 0 54px rgba(0, 0, 0, 0.52), 0 0 42px rgba(24, 217, 255, .08);
    box-sizing: border-box;
    color: var(--sdac-text);
    height: 100dvh;
    inset: 0 auto 0 0;
    max-width: min(82vw, calc(100dvw - clamp(1rem, 3vw, 1.5rem)));
    overflow: hidden;
    padding: clamp(3.75rem, 8dvh, 4.5rem) 0 clamp(0.75rem, 1.6vw, 1rem);
    position: fixed;
    transform: translateX(0);
    transition: transform .18s ease;
    width: min(var(--sdac-sidebar-width), 82dvw);
    z-index: 1001;
}
.sdac-sidebar * { box-sizing: border-box; max-width: 100%; min-width: 0; }
body.sdac-sidebar-collapsed .sdac-sidebar { transform: translateX(-105%); }
.sdac-sidebar-scroll {
    display: flex;
    flex-direction: column;
    gap: 0;
    height: 100%;
    overflow-x: hidden;
    overflow-y: auto;
    padding: 0 clamp(0.75rem, 1.6vw, 1rem);
    width: 100%;
}
.sdac-sidebar-scroll::-webkit-scrollbar { width: 0.5rem; }
.sdac-sidebar-scroll::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, .35); border-radius: 999px; }
.sdac-sidebar-brand { flex: 0 0 auto; font-size: clamp(1.05rem, 1.4vw, 1.25rem); font-weight: 900; margin-bottom: 0.625rem; }
.sdac-sidebar-user { color: var(--sdac-muted); flex: 0 0 auto; font-size: clamp(0.82rem, 1vw, 0.9rem); line-height: 1.35; margin-bottom: clamp(0.75rem, 1.4vw, 1.125rem); }
.sdac-sidebar-user span { color: var(--sdac-secondary); }
.sdac-sidebar-warning { border: 1px solid #f59e0b; border-radius: 8px; color: #fde68a; flex: 0 0 auto; font-size: .82rem; line-height: 1.35; margin: 0 0 14px; padding: 9px 10px; }
.sdac-server-switcher { align-items: stretch !important; border: 1px solid var(--sdac-border); border-radius: 8px; box-sizing: border-box !important; display: grid !important; flex: 0 0 auto; gap: 6px; grid-template-columns: minmax(0, 1fr); inline-size: 100% !important; margin: 0 0 14px !important; max-inline-size: 100% !important; max-width: 100% !important; min-inline-size: 0 !important; min-width: 0 !important; overflow: hidden; padding: 10px !important; width: 100% !important; }
.sdac-server-switcher label { box-sizing: border-box !important; color: var(--sdac-muted); display: block !important; font-size: .72rem; font-weight: 800; margin: 0 !important; max-width: 100%; min-width: 0; overflow: hidden; text-overflow: ellipsis; text-transform: uppercase; white-space: nowrap; }
.sdac-sidebar .sdac-server-switcher select, .sdac-sidebar .sdac-server-switcher button { align-self: stretch !important; box-sizing: border-box !important; display: block !important; font-size: .86rem !important; inline-size: 100% !important; line-height: 1.2 !important; margin: 0 !important; max-inline-size: 100% !important; max-width: 100% !important; min-inline-size: 0 !important; min-width: 0 !important; overflow: hidden !important; padding: 8px 10px !important; text-overflow: ellipsis; white-space: nowrap; width: 100% !important; }
.sdac-sidebar-nav { display: flex !important; flex: 0 0 auto; flex-direction: column !important; flex-wrap: nowrap !important; gap: 10px !important; margin: 0 !important; min-height: 0; overflow: visible; padding: 0; text-align: left !important; }
.sdac-sidebar-section { background: linear-gradient(180deg, rgba(17,24,43,.74), rgba(8,15,32,.78)); border: 1px solid var(--sdac-border); border-radius: 10px; flex: 0 0 auto; margin: 0; min-height: 0; overflow: hidden; box-shadow: 0 14px 32px rgba(0,0,0,.22); }
.sdac-sidebar-main-section { display: block; }
.sdac-sidebar-section-title { align-items: center; background: linear-gradient(90deg, rgba(139,92,246,.20), rgba(24,217,255,.08)); color: var(--sdac-text); cursor: pointer; display: flex; font-size: .75rem; font-weight: 900; gap: 8px; justify-content: space-between; letter-spacing: 0; line-height: 1.2; list-style: none; padding: 8px 10px; text-transform: uppercase; user-select: none; }
.sdac-sidebar-section-title::-webkit-details-marker { display: none; }
.sdac-sidebar-section-title::marker { content: ""; }
.sdac-sidebar-section.active .sdac-sidebar-section-title { background: linear-gradient(100deg, rgba(124,92,255,.86), rgba(24,217,255,.74)); color: #fff; box-shadow: 0 0 22px rgba(24,217,255,.18); }
.sdac-sidebar-section-caret { align-items: center; border: 1px solid color-mix(in srgb, var(--sdac-muted) 35%, transparent); border-radius: 999px; display: inline-flex; flex: 0 0 auto; font-size: .85rem; height: 1.15rem; justify-content: center; line-height: 1; width: 1.15rem; }
.sdac-sidebar-section[open] .sdac-sidebar-section-caret { transform: rotate(45deg); }
.sdac-sidebar-section-links { min-height: 0; overflow: visible; padding: 7px 6px 8px; width: 100%; }
.sdac-sidebar-link { border-radius: 7px; color: var(--sdac-text) !important; display: block; font-weight: 650; line-height: 1.25; margin: 2px 0; max-width: 100%; overflow-wrap: anywhere; padding: 9px 11px; text-decoration: none; white-space: normal; width: 100%; }
.sdac-sidebar-link:hover, .sdac-sidebar-link.active { color: #fff !important; background: linear-gradient(100deg, rgba(124,92,255,.92), rgba(24,217,255,.82)); box-shadow: 0 0 20px rgba(24, 217, 255, .24); }
.sdac-sidebar-invite { align-items: center; background: linear-gradient(100deg, #7c5cff, #18d9ff); box-shadow: 0 0 24px rgba(24,217,255,.22); border-radius: 8px; color: #fff !important; display: inline-flex; font-weight: 850; justify-content: center; line-height: 1.2; margin: 0 0 12px; min-height: 38px; overflow-wrap: anywhere; padding: 9px 12px; text-align: center; text-decoration: none; white-space: normal; width: 100%; }
.sdac-sidebar-invite:hover { color: #fff !important; filter: brightness(1.08); }
.sdac-sidebar-footer { border-top: 1px solid var(--sdac-border); flex: 0 0 auto; margin-top: 12px; overflow: visible; padding-top: 12px; width: 100%; }
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
body.sdac-theme main > h1:first-child {
    background: linear-gradient(100deg, #f8fbff 0%, #18d9ff 45%, #b45cff 88%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent !important;
    font-size: clamp(1.85rem, 3vw, 2.7rem) !important;
    letter-spacing: 0 !important;
    margin-bottom: .65rem !important;
    text-shadow: 0 0 30px rgba(24, 217, 255, .18);
}
body.sdac-theme h1, body.sdac-theme h2, body.sdac-theme h3 { color: var(--sdac-text) !important; letter-spacing: 0 !important; }
body.sdac-theme p, body.sdac-theme td, body.sdac-theme th, body.sdac-theme li { color: color-mix(in srgb, var(--sdac-text) 82%, var(--sdac-muted)) !important; }
body.sdac-theme th { color: var(--sdac-text) !important; font-weight: 850 !important; }
body.sdac-theme hr { border-color: var(--sdac-border) !important; }
body.sdac-theme input, body.sdac-theme select, body.sdac-theme textarea {
    background: rgba(248, 251, 255, .075) !important;
    border: 1px solid rgba(126, 151, 255, .24) !important;
    border-radius: 8px !important;
    color: var(--sdac-text) !important;
    min-height: 2.35rem;
}
body.sdac-theme input:focus, body.sdac-theme select:focus, body.sdac-theme textarea:focus {
    border-color: var(--sdac-secondary) !important;
    box-shadow: 0 0 0 3px rgba(34, 211, 238, .16) !important;
    outline: none !important;
}
body.sdac-theme button, body.sdac-theme input[type="submit"], body.sdac-theme .button, body.sdac-theme a.button {
    background: linear-gradient(100deg, #7c5cff, #18d9ff) !important;
    border: 1px solid rgba(248, 251, 255, .10) !important;
    border-radius: 10px !important;
    box-shadow: 0 14px 32px rgba(24, 217, 255, .18), 0 0 18px rgba(139, 92, 246, .10) !important;
    color: #fff !important;
    font-weight: 850 !important;
}
body.sdac-theme button:hover, body.sdac-theme input[type="submit"]:hover, body.sdac-theme .button:hover, body.sdac-theme a.button:hover {
    filter: brightness(1.08);
    transform: translateY(-1px);
}
body.sdac-theme img, body.sdac-theme video { border-radius: 8px; }
body.sdac-theme code, body.sdac-theme pre { background: rgba(2, 6, 23, .58) !important; border: 1px solid var(--sdac-border); border-radius: 8px; color: #dbeafe !important; }
body.sdac-theme .badge, body.sdac-theme .pill, body.sdac-theme .status, body.sdac-theme .tag {
    background: rgba(8, 15, 32, .72) !important;
    border-color: rgba(24, 217, 255, .30) !important;
    box-shadow: 0 0 18px rgba(24, 217, 255, .12) inset;
}
@media (max-width: 56rem) {
    body.sdac-has-sidebar,
    body.sdac-has-sidebar.sdac-sidebar-collapsed { padding-left: 0 !important; }
    body.sdac-has-sidebar main { padding-top: clamp(3rem, 8dvh, 3.75rem) !important; }
    .sdac-sidebar-controls { left: clamp(0.65rem, 2.5vw, 0.85rem) !important; top: clamp(0.65rem, 2.5vw, 0.85rem) !important; }
    .sdac-sidebar { border-radius: 0 0.875rem 0.875rem 0; box-shadow: 1.125rem 0 2.5rem rgba(2, 6, 23, 0.48); max-width: min(88dvw, calc(100dvw - 0.75rem)); transform: translateX(-105%); width: min(20rem, 88dvw); }
    body.sdac-sidebar-open .sdac-sidebar { transform: translateX(0); }
    body.sdac-sidebar-open .sdac-sidebar-controls { left: clamp(0.65rem, 2.5vw, 0.85rem) !important; }
    body.sdac-sidebar-open.sdac-menu-viewport-left .sdac-sidebar-controls { left: clamp(0.65rem, 2.5vw, 0.85rem) !important; }
}
</style>
"""