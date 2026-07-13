import type { CapacitorConfig } from "@capacitor/cli";

const directDashboardUrl = process.env.SDAC_APP_DIRECT_URL || "";
const appName = process.env.SDAC_APP_NAME || "SDACCompanion";

const config: CapacitorConfig = {
  appId: process.env.SDAC_APP_ID || "app.sdac.companion",
  appName,
  webDir: "dist",
  server: directDashboardUrl
    ? {
        url: directDashboardUrl,
        cleartext: directDashboardUrl.startsWith("http://")
      }
    : undefined,
  plugins: {
    App: {
      launchAutoHide: true
    }
  }
};

export default config;
