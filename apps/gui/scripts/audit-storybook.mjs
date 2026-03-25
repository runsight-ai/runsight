#!/usr/bin/env node
/**
 * Captures rendered HTML from each Storybook story's Default variant
 * and runs snug check on it.
 */
import { chromium } from 'playwright';
import { execSync } from 'child_process';
import { writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';

const STORYBOOK_URL = 'http://localhost:6006';
const OUT_DIR = '/tmp/storybook-audit';

// Default stories only — one per component
const STORIES = [
  'primitives-button--default',
  'primitives-badge--default',
  'primitives-icon--default',
  'primitives-avatar--default',
  'primitives-spinner--default',
  'primitives-divider--default',
  'primitives-link--default',
  'primitives-skeleton--default',
  'primitives-progress--default',
  'primitives-statusdot--default',
  'primitives-toast--default',
  'primitives-tooltip--default',
  'primitives-separator--default',
  'forms-input--default',
  'forms-textarea--default',
  'forms-checkbox--default',
  'forms-radio--default',
  'forms-switch--default',
  'forms-select--default',
  'forms-slider--default',
  'forms-inputgroup--with-prefix',
  'forms-label--default',
  'data-display-table--default',
  'data-display-card--default',
  'data-display-statcard--default',
  'data-display-codeblock--default',
  'data-display-actioncard--default',
  'data-display-keyvalue--default',
  'navigation-breadcrumb--default',
  'navigation-pagination--default',
  'navigation-tabs--default',
  'navigation-sidebar--default',
  'overlays-dialog--default',
  'overlays-sheet--default',
  'overlays-dropdownmenu--default',
  'overlays-popover--default',
  'overlays-command--default',
  'overlays-scrollarea--default',
  'composites-nodecard--default',
  'composites-appshell--default',
  'composites-emptystate--default',
];

async function main() {
  mkdirSync(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });

  const results = [];

  for (const storyId of STORIES) {
    const page = await context.newPage();
    const url = `${STORYBOOK_URL}/iframe.html?id=${storyId}&viewMode=story`;
    const componentName = storyId.split('--')[0].replace(/-/g, '_');
    const htmlFile = join(OUT_DIR, `${componentName}.html`);

    try {
      const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });

      if (!response || response.status() !== 200) {
        results.push({ component: componentName, storyId, status: 'FETCH_ERROR', errors: 0, warnings: 0, detail: `HTTP ${response?.status()}` });
        await page.close();
        continue;
      }

      // Wait for story to render
      await page.waitForTimeout(1500);

      // Check for React errors in the page
      const errors = await page.evaluate(() => {
        const errorEl = document.querySelector('[data-story-error]');
        if (errorEl) return errorEl.textContent;
        const sbError = document.querySelector('.sb-errordisplay');
        if (sbError) return sbError.textContent;
        return null;
      });

      if (errors) {
        results.push({ component: componentName, storyId, status: 'RENDER_ERROR', errors: 0, warnings: 0, detail: errors.slice(0, 200) });
        await page.close();
        continue;
      }

      // Get full HTML
      const html = await page.content();
      writeFileSync(htmlFile, html);

      // Run snug check
      try {
        const snugOutput = execSync(`snug check "${htmlFile}" --width 1280 --height 800 2>&1`, {
          timeout: 30000,
          encoding: 'utf-8',
        });

        // Parse summary from YAML output
        const errMatch = snugOutput.match(/errors:\s*(\d+)/);
        const warnMatch = snugOutput.match(/warnings:\s*(\d+)/);
        const errorCount = errMatch ? parseInt(errMatch[1]) : 0;
        const warningCount = warnMatch ? parseInt(warnMatch[1]) : 0;

        results.push({
          component: componentName,
          storyId,
          status: errorCount > 0 ? 'ISSUES' : 'OK',
          errors: errorCount,
          warnings: warningCount,
          detail: errorCount > 0 ? snugOutput.split('\n').filter(l => l.includes('error') || l.includes('severity: error')).slice(0, 5).join('; ') : '',
        });
      } catch (e) {
        // snug might exit non-zero on issues
        const output = e.stdout || e.stderr || e.message || '';
        const errMatch = output.match(/errors:\s*(\d+)/);
        const warnMatch = output.match(/warnings:\s*(\d+)/);
        results.push({
          component: componentName,
          storyId,
          status: 'SNUG_RAN',
          errors: errMatch ? parseInt(errMatch[1]) : -1,
          warnings: warnMatch ? parseInt(warnMatch[1]) : -1,
          detail: output.slice(0, 300),
        });
      }
    } catch (e) {
      results.push({ component: componentName, storyId, status: 'ERROR', errors: -1, warnings: -1, detail: e.message.slice(0, 200) });
    }

    await page.close();
  }

  await browser.close();

  // Print summary
  console.log('\n=== STORYBOOK AUDIT RESULTS ===\n');
  console.log('Component'.padEnd(40) + 'Status'.padEnd(15) + 'Errors'.padEnd(10) + 'Warnings'.padEnd(10) + 'Detail');
  console.log('-'.repeat(120));

  for (const r of results) {
    console.log(
      r.component.padEnd(40) +
      r.status.padEnd(15) +
      String(r.errors).padEnd(10) +
      String(r.warnings).padEnd(10) +
      (r.detail || '').slice(0, 60)
    );
  }

  const totalErrors = results.reduce((sum, r) => sum + Math.max(0, r.errors), 0);
  const totalWarnings = results.reduce((sum, r) => sum + Math.max(0, r.warnings), 0);
  const renderErrors = results.filter(r => r.status === 'RENDER_ERROR').length;
  const fetchErrors = results.filter(r => r.status === 'FETCH_ERROR').length;

  console.log('\n--- SUMMARY ---');
  console.log(`Total components: ${results.length}`);
  console.log(`Render errors: ${renderErrors}`);
  console.log(`Fetch errors: ${fetchErrors}`);
  console.log(`Snug errors: ${totalErrors}`);
  console.log(`Snug warnings: ${totalWarnings}`);

  // Write detailed results
  writeFileSync(join(OUT_DIR, 'audit-results.json'), JSON.stringify(results, null, 2));
  console.log(`\nDetailed results: ${join(OUT_DIR, 'audit-results.json')}`);
  console.log(`HTML dumps: ${OUT_DIR}/`);
}

main().catch(console.error);
