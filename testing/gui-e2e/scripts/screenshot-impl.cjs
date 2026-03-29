const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  
  const outDir = path.resolve(__dirname, '../../../.agora/workspace/flow5-settings');
  
  await page.goto('http://localhost:3000/settings');
  await page.waitForTimeout(2000); // Wait for load
  
  // Providers tab
  await page.screenshot({ path: path.join(outDir, 'review-impl-providers.png') });
  console.log('Saved review-impl-providers.png');
  
  // Models tab
  try {
    await page.click('text=Models');
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(outDir, 'review-impl-models.png') });
    console.log('Saved review-impl-models.png');
  } catch (e) { console.log('Could not screenshot Models tab', e.message); }
  
  // API Keys tab
  try {
    await page.click('text=API Keys');
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(outDir, 'review-impl-apikeys.png') });
    console.log('Saved review-impl-apikeys.png');
  } catch (e) { console.log('Could not screenshot API Keys tab', e.message); }
  
  // Budgets tab
  try {
    await page.click('text=Budgets');
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(outDir, 'review-impl-budgets.png') });
    console.log('Saved review-impl-budgets.png');
  } catch (e) { console.log('Could not screenshot Budgets tab', e.message); }
  
  // Add Provider modal (go back to Providers tab)
  try {
    await page.click('text=Providers');
    await page.waitForTimeout(1000);
    await page.click('text=Add Provider');
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(outDir, 'review-impl-add-provider.png') });
    console.log('Saved review-impl-add-provider.png');
  } catch (e) { console.log('Could not screenshot Add Provider modal', e.message); }

  await browser.close();
})();
