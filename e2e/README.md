# Clawthon E2E Tests

Playwright-based E2E tests for the management console and participant VMs.

## Setup

```bash
cd e2e
npm install
npx playwright install chromium
```

## Run

```bash
# Headless (CI)
npm test

# Headed (debug)
npm run test:headed

# Interactive UI
npm run test:ui
```

## Environment

Default target: `http://console.iseai.neuratools.ai`

Override: `CONSOLE_URL=http://localhost:8000 npm test`
