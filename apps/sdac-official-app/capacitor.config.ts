import type { CapacitorConfig } from "@capacitor/cli";

const directDashboardUrl = process.env.SDAC_APP_DIRECT_URL || "";
const appName = process.env.SDAC_APP_NAME || "Sana-Chan";

const config: CapacitorConfig = {
  appId: process.env.SDAC_APP_ID || "com.baytae.sanachan",
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
    },
    CapacitorHttp: {
      enabled: true
    }
  }
};

export default config;

