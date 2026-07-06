import type { CapacitorConfig } from "@capacitor/cli";

const dashboardUrl = process.env.SDAC_APP_DASHBOARD_URL || "";

const config: CapacitorConfig = {
  appId: "app.sdac.official",
  appName: "SDAC",
  webDir: "dist",
  bundledWebRuntime: false,
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
