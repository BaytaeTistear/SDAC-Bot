import "./styles.css";

type ServerRow = {
  id: string;
  name: string;
};

type BootstrapPayload = {
  app: {
    display_name: string;
    entry_url: string;
    icon_url: string;
  };
  auth: {
    account_logged_in: boolean;
    account_username: string;
    account_role: string;
    admin_logged_in: boolean;
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
  };
};

const dashboardBase = (import.meta.env.VITE_SDAC_DASHBOARD_URL || "https://freethefishies.us.to").replace(/\/$/, "");
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

function routeButton(label: string, route: string): string {
  return `<a class="action" href="${escapeHtml(absoluteUrl(route))}">${escapeHtml(label)}</a>`;
}

function render(payload: BootstrapPayload): void {
  applyTheme(payload);
  const routes = payload.routes || {};
  const loggedIn = payload.auth.account_logged_in || payload.auth.admin_logged_in;
  const serverOptions = payload.server.servers
    .map((server) => `<option value="${escapeHtml(server.id)}" ${server.id === payload.server.selected_guild_id ? "selected" : ""}>${escapeHtml(server.name)}</option>`)
    .join("");
  const accountLabel = loggedIn
    ? `${payload.auth.account_username || "Admin"} (${payload.auth.admin_role || payload.auth.account_role})`
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
        ${!loggedIn && payload.auth.discord_oauth_enabled ? routeButton("Login with Discord", routes.discord_login) : ""}
        ${routeButton("Submissions", routes.submissions)}
        ${routeButton("Guessing", routes.guessing)}
        ${routeButton("Servers", routes.servers)}
        ${routeButton("Releases", routes.admin_releases)}
      </section>
      <section class="panel muted">
        <strong>Release</strong>
        <span>${escapeHtml(payload.release.installed)} via ${escapeHtml(payload.release.configured_tag)}</span>
      </section>
      <iframe title="SDAC Dashboard" src="${escapeHtml(absoluteUrl(payload.app.entry_url))}"></iframe>
    </main>
  `;

  document.querySelector<HTMLSelectElement>("#server-select")?.addEventListener("change", (event) => {
    const guildId = (event.target as HTMLSelectElement).value;
    window.location.href = absoluteUrl(`${routes.submissions || "/"}?guild_id=${encodeURIComponent(guildId)}`);
  });
}

function renderError(error: unknown): void {
  appRoot!.innerHTML = `
    <main class="shell">
      <section class="panel">
        <h1>SDAC</h1>
        <p>Could not reach the SDAC dashboard backend.</p>
        <p class="muted">${escapeHtml(String(error))}</p>
        <a class="action" href="${escapeHtml(dashboardBase)}">Open Dashboard</a>
      </section>
    </main>
  `;
}

fetch(absoluteUrl("/api/app/bootstrap"), { credentials: "include" })
  .then((response) => {
    if (!response.ok) throw new Error(`Bootstrap failed: ${response.status}`);
    return response.json() as Promise<BootstrapPayload>;
  })
  .then(render)
  .catch(renderError);
