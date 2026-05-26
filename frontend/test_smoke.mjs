import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';

const APP_URL = 'http://127.0.0.1:5175';
const SCREENSHOT_DIR = path.dirname(fileURLToPath(import.meta.url));

const errors = [];

async function main() {
  console.log('[1/5] Launching headless Chromium...');
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(`[CONSOLE ERROR] ${msg.text()}`);
  });
  page.on('pageerror', (err) => errors.push(`[PAGE ERROR] ${err.message}`));

  console.log('[2/5] Navigating to app...');
  await page.goto(APP_URL, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  console.log('[3/5] Taking initial screenshot...');
  await page.screenshot({ path: `${SCREENSHOT_DIR}/screenshot_initial.png`, fullPage: false });

  // Check page title and key elements
  const title = await page.title();
  console.log(`    Page title: "${title}"`);
  const headerText = await page.textContent('h1');
  console.log(`    Header text: "${headerText}"`);

  // Check if any Ant Design components rendered
  const antCards = await page.locator('.ant-card').count();
  console.log(`    Ant Design Cards: ${antCards}`);

  // Try clicking the document type selector
  console.log('[4/5] Testing interactions...');
  const docTypeSelector = page.locator('.ant-select').last();
  if (await docTypeSelector.isVisible()) {
    console.log('    Doc type selector: VISIBLE');
  }

  // Check mode segmented control
  const segmented = page.locator('.ant-segmented');
  const segCount = await segmented.count();
  console.log(`    Segmented controls: ${segCount}`);

  // Type in the textarea
  const textarea = page.locator('textarea').first();
  if (await textarea.isVisible()) {
    await textarea.fill('2026年5月20日，张三在北京市朝阳区某商场内盗窃一部手机，价值5000元。');
    console.log('    Textarea fill: OK');
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/screenshot_filled.png`, fullPage: false });
  }

  // Switch to manual mode
  const manualBtn = page.locator('.ant-segmented .ant-segmented-item').nth(1);
  if (await manualBtn.isVisible()) {
    await manualBtn.click();
    await page.waitForTimeout(1000);
    console.log('    Switched to manual mode');
    await page.screenshot({ path: `${SCREENSHOT_DIR}/screenshot_manual.png`, fullPage: false });
  }

  console.log('[5/5] Checking for errors...');
  if (errors.length > 0) {
    console.log(`    FOUND ${errors.length} ERROR(S):`);
    errors.forEach((e) => console.log(`    - ${e}`));
  } else {
    console.log('    No console errors!');
  }

  await browser.close();
  console.log('\nDONE. Screenshots saved to:');
  console.log(`  ${SCREENSHOT_DIR}/screenshot_initial.png`);
  console.log(`  ${SCREENSHOT_DIR}/screenshot_filled.png`);
  console.log(`  ${SCREENSHOT_DIR}/screenshot_manual.png`);

  process.exit(errors.length > 0 ? 1 : 0);
}

main().catch((err) => {
  console.error('FATAL:', err.message);
  process.exit(1);
});
