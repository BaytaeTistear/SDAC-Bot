import { defineConfig } from '@playwright/test';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const pythonCommand = process.platform === 'win32' ? 'py -3.12 ../dashboard.py' : 'python ../dashboard.py';

export default defineConfig({
  testDir: './tests',
  retries: 1,
  use: { baseURL: process.env.SDAC_E2E_URL || 'http://127.0.0.1:5000', trace: 'retain-on-failure' },
  webServer: process.env.SDAC_E2E_URL ? undefined : {
    command: pythonCommand,
    url: 'http://127.0.0.1:5000/health',
    reuseExistingServer: false,
    cwd: __dirname,
    env: {
      ...process.env,
      SDAC_ADMIN_KEY: 'e2e-admin-key',
      SDAC_SECRET_KEY: 'e2e-secret-key',
      SDAC_DB_FILE: join(tmpdir(), 'sdac-e2e.db'),
      SDAC_CONFIG_FILE: join(tmpdir(), 'sdac-e2e-config.json'),
    },
  },
});
