import type { CapacitorConfig } from "@capacitor/cli";

const dashboardUrl = process.env.SDAC_APP_DASHBOARD_URL || "https://freethefishies.us.to";
const appName = process.env.SDAC_APP_NAME || "SDACCompanion";

const config: CapacitorConfig = {
  appId: process.env.SDAC_APP_ID || "app.sdac.companion",
  appName,
  webDir: "dist",
  server: dashboardUrl
    ? {
        url: dashboardUrl,
        cleartext: dashboardUrl.startsWith("http://")
      }
    : undefined,
  plugins: {
    App: {
      launchAutoHide: true
    }
  }
};

export default config;
