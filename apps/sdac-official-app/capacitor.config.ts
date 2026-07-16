import type { CapacitorConfig } from "@capacitor/cli";

const appName = process.env.SANA_APP_NAME || process.env.SDAC_APP_NAME || "Sana-Chan";

const config: CapacitorConfig = {
  appId: process.env.SANA_APP_ID || process.env.SDAC_APP_ID || "com.baytae.sanachan",
  appName,
  webDir: "dist",
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

