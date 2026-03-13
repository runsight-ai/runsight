const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  
  const outDir = path.resolve(__dirname, '../../.agora/workspace/flow5-settings');
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const mockups = [
    { file: '01-settings-providers/mockup.html', out: 'review-mockup-01.png' },
    { file: '02-settings-models/mockup.html', out: 'review-mockup-02.png' },
    { file: '03-settings-api-keys/mockup.html', out: 'review-mockup-03.png' },
    { file: '04-settings-budgets/mockup.html', out: 'review-mockup-04.png' },
    { file: '05-add-provider-modal/mockup.html', out: 'review-mockup-05.png' }
  ];

  for (const m of mockups) {
    const fileUrl = 'file://' + path.resolve(__dirname, '../../.agora/mockups/flow-5-settings', m.file);
    await page.goto(fileUrl);
    await page.screenshot({ path: path.join(outDir, m.out) });
    console.log(`Saved ${m.out}`);
  }

  await browser.close();
})();
