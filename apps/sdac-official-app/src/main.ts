import "./styles.css";
import { App } from "@capacitor/app";
import { AppLauncher } from "@capacitor/app-launcher";
import { Browser } from "@capacitor/browser";
import { Capacitor, CapacitorHttp } from "@capacitor/core";

type ServerRow = {
  id: string;
  name: string;
};

type BootstrapPayload = {
  app: {
    display_name: string;
    entry_url: string;
    icon_url: string;
    invite_url: string;
    github_url: string;
    wiki_url: string;
    version: string;
  };
  auth: {
    account_logged_in: boolean;
    account_username: string;
    account_role: string;
    admin_logged_in: boolean;
    admin_username: string;
    admin_role: string;
    discord_oauth_enabled: boolean;
  };
  theme: Record<string, string>;
  layout: Record<string, string>;
  server: {
    selected_guild_id: string;
    servers: ServerRow[];
  };
  routes: Record<string, string>;
  release: {
    installed: string;
    configured_tag: string;
    installed_version: string;
    official_version: string;
    experimental_version: string;
    official_tag: string;
    experimental_tag: string;
    official_release_url: string;
    experimental_release_url: string;
    official_apk_url: string;
    experimental_apk_url: string;
    official_apk_sha256_url: string;
    experimental_apk_sha256_url: string;
    official_apk_sha256: string;
    experimental_apk_sha256: string;
    update_available: boolean;
    recommended_channel: string;
  };
  diagnostics: {
    dashboard_url: string;
    native: boolean;
    platform: string;
    session_cookie_seen: boolean;
    account_session_seen: boolean;
    admin_session_seen: boolean;
  };
};

type UpdateChannel = "experimental" | "official";

type UpdateChannelInfo = {
  channel: UpdateChannel;
  label: string;
  tag: string;
  version: string;
  releaseUrl: string;
  apkUrl: string;
  sha256Url: string;
  sha256: string;
};

const APP_SHELL_VERSION = "4.2.20";
const dashboardBase = (import.meta.env.VITE_SDAC_DASHBOARD_URL || "https://freethefishies.us.to").replace(/\/$/, "");
const nativePlatform = Capacitor.getPlatform();
const isNative = Capacitor.isNativePlatform();
const appRoot = document.querySelector<HTMLDivElement>("#app");

function absoluteUrl(path: string): string {
  if (!path) return dashboardBase;
  if (/^https?:\/\//i.test(path)) return path;
  return `${dashboardBase}${path.startsWith("/") ? "" : "/"}${path}`;
}

function escapeHtml(value: string): string {
  return String(value).replace(/[&<>"']/g, (character) => {
    const replacements: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\"": "&quot;",
      "'": "&#39;"
    };
    return replacements[character] || character;
  });
}

function applyTheme(payload: BootstrapPayload): void {
  const root = document.documentElement;
  const theme = payload.theme || {};
  const layout = payload.layout || {};
  const vars: Record<string, string> = {
    "--sdac-primary": theme.primary || "#4f46e5",
    "--sdac-secondary": theme.secondary || "#06b6d4",
    "--sdac-accent": theme.accent || "#f59e0b",
    "--sdac-bg": theme.background || "#0f172a",
    "--sdac-surface": theme.surface || "#111827",
    "--sdac-text": theme.text || "#f8fafc",
    "--sdac-muted": theme.muted || "#94a3b8",
    "--sdac-radius": `${layout.card_radius || "8"}px`
  };
  Object.entries(vars).forEach(([key, value]) => root.style.setProperty(key, value));
}

function routeButton(label: string, route: string, extraClass = ""): string {
  const className = `action ${extraClass}`.trim();
  return `<a class="${escapeHtml(className)}" href="${escapeHtml(absoluteUrl(route))}">${escapeHtml(label)}</a>`;
}

function externalButton(label: string, url: string, extraClass = ""): string {
  const disabled = url ? "" : " disabled";
  const className = `action ${extraClass}`.trim();
  return `<button class="${escapeHtml(className)}" type="button" data-app-action="open-url" data-url="${escapeHtml(url)}"${disabled}>${escapeHtml(label)}</button>`;
}

function appFrameUrl(route: string): string {
  const url = new URL(absoluteUrl(route));
  url.searchParams.set("sdac_app", "1");
  return url.toString();
}

function appButton(label: string, action: string, extraClass = ""): string {
  const className = `action ${extraClass}`.trim();
  return `<button class="${escapeHtml(className)}" type="button" data-app-action="${escapeHtml(action)}">${escapeHtml(label)}</button>`;
}

function versionParts(value: string): number[] {
  const match = String(value || "").match(/\d+(?:\.\d+)*/);
  return match ? match[0].split(".").map((part) => Number.parseInt(part, 10) || 0) : [];
}

function compareVersions(left: string, right: string): number {
  const a = versionParts(left);
  const b = versionParts(right);
  const length = Math.max(a.length, b.length);
  for (let index = 0; index < length; index += 1) {
    const delta = (a[index] || 0) - (b[index] || 0);
    if (delta) return delta;
  }
  return 0;
}

function channelInfo(payload: BootstrapPayload, channel: UpdateChannel): UpdateChannelInfo {
  const release = payload.release || {};
  if (channel === "official") {
    return {
      channel,
      label: "Official",
      tag: release.official_tag || "latest-official",
      version: release.official_version || "unknown",
      releaseUrl: release.official_release_url || `${payload.app.github_url}/releases/tag/latest-official`,
      apkUrl: release.official_apk_url || "",
      sha256Url: release.official_apk_sha256_url || "",
      sha256: release.official_apk_sha256 || ""
    };
  }
  return {
    channel,
    label: "Experimental",
    tag: release.experimental_tag || "latest-experimental",
    version: release.experimental_version || "unknown",
    releaseUrl: release.experimental_release_url || `${payload.app.github_url}/releases/tag/latest-experimental`,
    apkUrl: release.experimental_apk_url || "",
    sha256Url: release.experimental_apk_sha256_url || "",
    sha256: release.experimental_apk_sha256 || ""
  };
}

function updateChannelCard(info: UpdateChannelInfo, recommended: boolean): string {
  const newer = info.version !== "unknown" && compareVersions(info.version, APP_SHELL_VERSION) > 0;
  const cardClass = `update-channel${recommended ? " recommended" : ""}${newer ? " newer" : ""}`;
  const status = newer ? "Update available" : info.version === "unknown" ? "Release unknown" : "No newer APK detected";
  const shaDisplay = info.sha256 ? info.sha256 : "Open checksum file from the release.";
  return `
    <article class="${cardClass}">
      <div>
        <span class="eyebrow">${escapeHtml(info.label)} channel${recommended ? " · recommended" : ""}</span>
        <strong>${escapeHtml(info.version)}</strong>
        <p>${escapeHtml(status)} · ${escapeHtml(info.tag)}</p>
      </div>
      <dl>
        <dt>APK SHA256</dt>
        <dd><code>${escapeHtml(shaDisplay)}</code></dd>
      </dl>
      <div class="button-row compact">
        ${externalButton("Download APK", info.apkUrl)}
        ${externalButton("Checksum", info.sha256Url, "secondary")}
        ${externalButton("Release", info.releaseUrl, "secondary")}
        <button class="action secondary" type="button" data-app-action="copy-sha" data-sha="${escapeHtml(info.sha256)}" ${info.sha256 ? "" : "disabled"}>Copy SHA</button>
      </div>
    </article>
  `;
}

function releaseNotice(payload: BootstrapPayload): string {
  const release = payload.release || {};
  const recommendedChannel: UpdateChannel = release.recommended_channel === "latest-official" ? "official" : "experimental";
  const official = channelInfo(payload, "official");
  const experimental = channelInfo(payload, "experimental");
  const recommended = recommendedChannel === "official" ? official : experimental;
  const newer = recommended.version !== "unknown" && compareVersions(recommended.version, APP_SHELL_VERSION) > 0;
  const noticeClass = newer ? "panel update-card warn" : "panel update-card";
  const title = newer ? "App update available" : "App update status";
  return `
    <section class="${noticeClass}">
      <div class="update-heading">
        <div>
          <strong>${escapeHtml(title)}</strong>
          <span>Installed APK ${escapeHtml(APP_SHELL_VERSION)} · recommended ${escapeHtml(recommended.label)} ${escapeHtml(recommended.version)}</span>
        </div>
        <button class="action secondary" type="button" data-app-action="refresh">Refresh</button>
      </div>
      <div class="update-grid">
        ${updateChannelCard(experimental, recommendedChannel === "experimental")}
        ${updateChannelCard(official, recommendedChannel === "official")}
      </div>
      <ol class="install-steps">
        <li>Tap Download APK for the channel you want.</li>
        <li>If Android asks, allow this browser/app to install unknown apps.</li>
        <li>Open the downloaded APK and approve the Android installer prompt.</li>
        <li>After install, reopen SDACCompanion and check this panel again.</li>
      </ol>
    </section>
  `;
}

function diagnosticsPanel(payload: BootstrapPayload): string {
  const loggedIn = payload.auth.account_logged_in || payload.auth.admin_logged_in;
  return `
    <details class="panel diagnostics">
      <summary>App Diagnostics</summary>
      <dl>
        <dt>Dashboard</dt><dd>${escapeHtml(payload.diagnostics.dashboard_url)}</dd>
        <dt>App shell</dt><dd>${escapeHtml(APP_SHELL_VERSION)}</dd>
        <dt>Backend version</dt><dd>${escapeHtml(payload.app.version || payload.release.installed || "development")}</dd>
        <dt>Platform</dt><dd>${escapeHtml(payload.diagnostics.platform || nativePlatform)}</dd>
        <dt>Login</dt><dd>${loggedIn ? "Signed in" : "Signed out"}</dd>
        <dt>Cookie seen</dt><dd>${payload.diagnostics.session_cookie_seen ? "Yes" : "No"}</dd>
        <dt>Account session</dt><dd>${payload.diagnostics.account_session_seen ? "Yes" : "No"}</dd>
        <dt>Admin session</dt><dd>${payload.diagnostics.admin_session_seen ? "Yes" : "No"}</dd>
      </dl>
      <div class="button-row">
        ${appButton("Refresh Status", "refresh", "secondary")}
        ${appButton("Reset App Login", "reset-login", "danger")}
      </div>
    </details>
  `;
}

async function loadBootstrap(): Promise<BootstrapPayload> {
  const url = absoluteUrl("/api/app/bootstrap");
  try {
    const response = await fetch(url, { credentials: "include", cache: "no-store" });
    if (!response.ok) throw new Error(`Bootstrap failed: ${response.status}`);
    return await response.json() as BootstrapPayload;
  } catch (fetchError) {
    if (!isNative) throw fetchError;
    const nativeResponse = await CapacitorHttp.get({
      url,
      headers: { Accept: "application/json" },
      connectTimeout: 15000,
      readTimeout: 15000,
      responseType: "json"
    });
    if (nativeResponse.status < 200 || nativeResponse.status >= 300) {
      throw new Error(`Native bootstrap failed: ${nativeResponse.status}`);
    }
    return nativeResponse.data as BootstrapPayload;
  }
}

async function refreshBootstrap(): Promise<void> {
  render(await loadBootstrap());
}

async function openNativeBrowser(route: string): Promise<void> {
  const url = absoluteUrl(route);
  if (isNative) {
    await Browser.open({ url, presentationStyle: "fullscreen" });
    return;
  }
  window.location.href = url;
}

async function openExternalUrl(url: string): Promise<void> {
  if (!url) return;
  if (isNative) {
    try {
      await AppLauncher.openUrl({ url });
      return;
    } catch (error) {
      console.warn("External URL launch failed; falling back to Capacitor Browser", error);
      await Browser.open({ url, presentationStyle: "fullscreen" });
      return;
    }
  }
  window.location.href = url;
}

async function openExternalBrowser(route: string): Promise<void> {
  await openExternalUrl(absoluteUrl(route));
}

async function claimAppLogin(ticket: string): Promise<void> {
  if (!ticket) throw new Error("Missing app login ticket.");
  const url = absoluteUrl("/api/app/claim-login");
  if (isNative) {
    const nativeResponse = await CapacitorHttp.post({
      url,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      data: { ticket },
      connectTimeout: 15000,
      readTimeout: 15000,
      responseType: "json"
    });
    if (nativeResponse.status < 200 || nativeResponse.status >= 300 || nativeResponse.data?.ok === false) {
      throw new Error(nativeResponse.data?.error || `App login claim failed: ${nativeResponse.status}`);
    }
    await refreshBootstrap();
    return;
  }
  const response = await fetch(url, {
    method: "POST",
    credentials: "include",
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ ticket })
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `App login claim failed: ${response.status}`);
  }
  await refreshBootstrap();
}

async function handleAppUrlOpen(url: string): Promise<void> {
  const parsed = new URL(url);
  if (parsed.protocol !== "sdaccompanion:" || parsed.hostname !== "login-complete") {
    await refreshBootstrap();
    return;
  }
  await claimAppLogin(parsed.searchParams.get("ticket") || "");
}

async function resetAppLogin(): Promise<void> {
  try {
    localStorage.clear();
    sessionStorage.clear();
  } catch (error) {
    console.warn("Could not clear local app storage", error);
  }
  const logoutUrl = absoluteUrl("/account/logout");
  const frame = document.querySelector<HTMLIFrameElement>("iframe");
  if (frame) {
    frame.src = logoutUrl;
  } else {
    await fetch(logoutUrl, { credentials: "include", cache: "no-store" }).catch(() => undefined);
  }
  window.setTimeout(() => refreshBootstrap().catch(renderError), 900);
}

async function copySha(value: string): Promise<void> {
  if (!value) return;
  await navigator.clipboard.writeText(value).catch(() => undefined);
}

function wireAppActions(payload: BootstrapPayload): void {
  document.querySelectorAll<HTMLButtonElement>("[data-app-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.appAction || "";
      button.disabled = true;
      try {
        if (action === "discord-login") {
          await openExternalBrowser(payload.routes.discord_login);
        } else if (action === "reset-login") {
          await resetAppLogin();
        } else if (action === "refresh") {
          await refreshBootstrap();
        } else if (action === "invite") {
          await openNativeBrowser(payload.app.invite_url || payload.routes.invite);
        } else if (action === "open-url") {
          await openExternalUrl(button.dataset.url || "");
        } else if (action === "copy-sha") {
          await copySha(button.dataset.sha || "");
        }
      } finally {
        button.disabled = false;
      }
    });
  });
}

function render(payload: BootstrapPayload): void {
  applyTheme(payload);
  const routes = payload.routes || {};
  const loggedIn = payload.auth.account_logged_in || payload.auth.admin_logged_in;
  const serverOptions = payload.server.servers
    .map((server) => `<option value="${escapeHtml(server.id)}" ${server.id === payload.server.selected_guild_id ? "selected" : ""}>${escapeHtml(server.name)}</option>`)
    .join("");
  const accountLabel = loggedIn
    ? `${payload.auth.account_username || payload.auth.admin_username || "Admin"} (${payload.auth.admin_role || payload.auth.account_role})`
    : "Guest";

  appRoot!.innerHTML = `
    <main class="shell">
      <section class="hero">
        <img src="/sdac-companion-art.png" alt="" />
        <div>
          <h1>${escapeHtml(payload.app.display_name)}</h1>
          <p>${escapeHtml(accountLabel)}</p>
        </div>
      </section>
      <section class="panel">
        <label for="server-select">Server</label>
        <select id="server-select">
          <option value="all">All Allowed Servers</option>
          ${serverOptions}
        </select>
      </section>
      <section class="actions">
        ${routeButton("Open Dashboard", routes.home)}
        ${loggedIn ? routeButton("My Account", routes.account) : routeButton("Login", routes.login)}
        ${!loggedIn && payload.auth.discord_oauth_enabled ? appButton("Login with Discord", "discord-login") : ""}
        ${appButton("Reset App Login", "reset-login", "secondary")}
        ${payload.app.invite_url || routes.invite ? appButton("Invite Bot", "invite", "secondary") : ""}
        ${routeButton("Submissions", routes.submissions)}
        ${routeButton("Guessing", routes.guessing)}
        ${routeButton("Servers", routes.servers)}
        ${routeButton("Releases", routes.admin_releases)}
      </section>
      ${releaseNotice(payload)}
      ${diagnosticsPanel(payload)}
      <iframe title="SDAC Dashboard" src="${escapeHtml(appFrameUrl(payload.app.entry_url))}"></iframe>
    </main>
  `;

  document.querySelector<HTMLSelectElement>("#server-select")?.addEventListener("change", (event) => {
    const guildId = (event.target as HTMLSelectElement).value;
    window.location.href = absoluteUrl(`${routes.submissions || "/"}?guild_id=${encodeURIComponent(guildId)}`);
  });
  wireAppActions(payload);
}

function renderError(error: unknown): void {
  appRoot!.innerHTML = `
    <main class="shell">
      <section class="panel diagnostics" open>
        <h1>SDAC</h1>
        <p>Could not reach the SDAC dashboard backend.</p>
        <p class="muted">${escapeHtml(String(error))}</p>
        <dl>
          <dt>Dashboard</dt><dd>${escapeHtml(dashboardBase)}</dd>
          <dt>App shell</dt><dd>${escapeHtml(APP_SHELL_VERSION)}</dd>
          <dt>Platform</dt><dd>${escapeHtml(nativePlatform)}</dd>
          <dt>Native app</dt><dd>${isNative ? "Yes" : "No"}</dd>
        </dl>
        <div class="button-row">
          <button class="action" type="button" data-error-action="retry">Retry</button>
          <button class="action secondary" type="button" data-error-action="browser">Open Dashboard</button>
        </div>
      </section>
    </main>
  `;
  document.querySelector<HTMLButtonElement>("[data-error-action='retry']")?.addEventListener("click", () => {
    loadBootstrap().then(render).catch(renderError);
  });
  document.querySelector<HTMLButtonElement>("[data-error-action='browser']")?.addEventListener("click", () => {
    openNativeBrowser(dashboardBase).catch(() => {
      window.location.href = dashboardBase;
    });
  });
}

loadBootstrap()
  .then(render)
  .catch(renderError);

App.addListener("appUrlOpen", (event) => {
  Browser.close().catch(() => undefined);
  handleAppUrlOpen(event.url).catch(renderError);
});
