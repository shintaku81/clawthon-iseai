import { defineConfig, devices } from '@playwright/test';

const isLocal = !!process.env.CONSOLE_URL?.includes('localhost');

export default defineConfig({
  testDir: './tests',
  timeout: isLocal ? 15000 : 30000,
  retries: isLocal ? 0 : 1,
  use: {
    baseURL: process.env.CONSOLE_URL || 'http://console.iseai.neuratools.ai',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    ignoreHTTPSErrors: isLocal,
  },
  // ローカルテスト時はparticipant-vmテストをスキップ（本番VM不要）
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      testIgnore: isLocal ? ['**/participant-vm.spec.ts'] : [],
    },
  ],
});
