#!/usr/bin/env node
/**
 * Captures screenshots of each component from both the reference HTML and
 * Storybook, saving them side-by-side in /tmp/visual-compare/ for manual
 * visual diffing.
 *
 * Run from apps/gui/:
 *   node scripts/visual-compare.mjs
 *
 * Prerequisites: Storybook running at http://localhost:6006
 */

import { chromium } from 'playwright';
import { mkdirSync } from 'fs';
import { join } from 'path';

const STORYBOOK_BASE = 'http://localhost:6006';
const REFERENCE_HTML = 'file:///Users/nataly/Documents/github/observatory/product-design-system/screens/component-library.html';
const OUT_DIR = '/tmp/visual-compare';
const REF_DIR = join(OUT_DIR, 'ref');
const SB_DIR = join(OUT_DIR, 'sb');

// Map: section ID in reference HTML → Storybook story ID
const COMPONENT_MAP = [
  { name: 'buttons',      sectionId: 'buttons',      storyId: 'primitives-button--all-variants' },
  { name: 'badges',       sectionId: 'badges',        storyId: 'primitives-badge--all-variants' },
  { name: 'icons',        sectionId: 'icons',         storyId: 'primitives-icon--all-sizes' },
  { name: 'avatar',       sectionId: 'avatar',        storyId: 'primitives-avatar--default' },
  { name: 'spinner',      sectionId: 'spinner',       storyId: 'primitives-spinner--all-variants' },
  { name: 'divider',      sectionId: 'divider',       storyId: 'primitives-divider--default' },
  { name: 'link',         sectionId: 'link',          storyId: 'primitives-link--all-variants' },
  { name: 'skeleton',     sectionId: 'skeleton',      storyId: 'primitives-skeleton--all-variants' },
  { name: 'progress',     sectionId: 'progress',      storyId: 'primitives-progress--variants' },
  { name: 'status-dots',  sectionId: 'status-dots',   storyId: 'primitives-statusdot--all-variants' },
  { name: 'toast',        sectionId: 'toast',         storyId: 'primitives-toast--all-variants' },
  { name: 'input',        sectionId: 'input',         storyId: 'forms-input--with-label' },
  { name: 'textarea',     sectionId: 'textarea',      storyId: 'forms-textarea--default' },
  { name: 'checkbox',     sectionId: 'checkbox',      storyId: 'forms-checkbox--group' },
  { name: 'radio',        sectionId: 'radio',         storyId: 'forms-radio--default' },
  { name: 'switch',       sectionId: 'switch',        storyId: 'forms-switch--showcase' },
  { name: 'select',       sectionId: 'select',        storyId: 'forms-select--default' },
  { name: 'slider',       sectionId: 'slider',        storyId: 'forms-slider--default' },
  { name: 'table',        sectionId: 'table',         storyId: 'data-display-table--default' },
  { name: 'card',         sectionId: 'card',          storyId: 'data-display-card--default' },
  { name: 'stat-card',    sectionId: 'stat-card',     storyId: 'data-display-statcard--all-variants' },
  { name: 'code-block',   sectionId: 'code-block',    storyId: 'data-display-codeblock--yaml' },
  { name: 'kv',           sectionId: 'kv',            storyId: 'data-display-keyvalue--list' },
  { name: 'empty-state',  sectionId: 'empty-state',   storyId: 'composites-emptystate--with-action' },
  { name: 'tabs',         sectionId: 'tabs',          storyId: 'navigation-tabs--default' },
  { name: 'breadcrumb',   sectionId: 'breadcrumb',    storyId: 'navigation-breadcrumb--default' },
  { name: 'pagination',   sectionId: 'pagination',    storyId: 'navigation-pagination--default' },
  { name: 'modal',        sectionId: 'modal',         storyId: 'overlays-dialog--default' },
  { name: 'dropdown',     sectionId: 'dropdown',      storyId: 'overlays-dropdownmenu--default' },
  { name: 'node-card',    sectionId: 'node-card',     storyId: 'composites-nodecard--all-categories' },
];

async function screenshotRef(page, sectionId, destPath) {
  await page.goto(REFERENCE_HTML, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  const canvas = await page.$(`#${sectionId} .showcase__canvas`);
  if (!canvas) {
    throw new Error(`Element #${sectionId} .showcase__canvas not found`);
  }
  await canvas.screenshot({ path: destPath });
}

async function screenshotStorybook(page, storyId, destPath) {
  const url = `${STORYBOOK_BASE}/iframe.html?id=${storyId}&viewMode=story`;
  const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });

  if (!response || response.status() !== 200) {
    throw new Error(`HTTP ${response?.status() ?? 'no response'}`);
  }

  await page.waitForTimeout(2000);

  const root = await page.$('#storybook-root');
  if (!root) {
    throw new Error('#storybook-root not found');
  }
  await root.screenshot({ path: destPath });
}

async function main() {
  mkdirSync(REF_DIR, { recursive: true });
  mkdirSync(SB_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });

  const results = [];

  for (const component of COMPONENT_MAP) {
    const refPath = join(REF_DIR, `${component.name}.png`);
    const sbPath = join(SB_DIR, `${component.name}.png`);
    let refStatus = 'CAPTURED';
    let sbStatus = 'CAPTURED';
    let refError = '';
    let sbError = '';

    // Reference screenshot
    {
      const page = await context.newPage();
      try {
        await screenshotRef(page, component.sectionId, refPath);
      } catch (e) {
        refStatus = 'FAILED';
        refError = e.message.slice(0, 80);
      } finally {
        await page.close();
      }
    }

    // Storybook screenshot
    {
      const page = await context.newPage();
      try {
        await screenshotStorybook(page, component.storyId, sbPath);
      } catch (e) {
        sbStatus = 'FAILED';
        sbError = e.message.slice(0, 80);
      } finally {
        await page.close();
      }
    }

    const overallStatus = refStatus === 'CAPTURED' && sbStatus === 'CAPTURED' ? 'CAPTURED' : 'FAILED';

    results.push({
      name: component.name,
      refStatus,
      refError,
      sbStatus,
      sbError,
      overallStatus,
    });

    // Live progress
    const indicator = overallStatus === 'CAPTURED' ? 'OK' : 'FAIL';
    console.log(`[${indicator}] ${component.name}`);
  }

  await browser.close();

  // Summary table
  const COL_NAME = 22;
  const COL_STATUS = 12;
  const COL_ERROR = 36;

  console.log('\n=== VISUAL COMPARE RESULTS ===\n');
  console.log(
    'Component'.padEnd(COL_NAME) +
    'Ref'.padEnd(COL_STATUS) +
    'Storybook'.padEnd(COL_STATUS) +
    'Status'.padEnd(COL_STATUS) +
    'Notes'
  );
  console.log('-'.repeat(COL_NAME + COL_STATUS + COL_STATUS + COL_STATUS + COL_ERROR));

  for (const r of results) {
    const notes = [r.refError && `ref: ${r.refError}`, r.sbError && `sb: ${r.sbError}`]
      .filter(Boolean)
      .join(' | ');
    console.log(
      r.name.padEnd(COL_NAME) +
      r.refStatus.padEnd(COL_STATUS) +
      r.sbStatus.padEnd(COL_STATUS) +
      r.overallStatus.padEnd(COL_STATUS) +
      notes
    );
  }

  const captured = results.filter(r => r.overallStatus === 'CAPTURED').length;
  const failed = results.filter(r => r.overallStatus === 'FAILED').length;

  console.log(`\n--- SUMMARY ---`);
  console.log(`Total components : ${results.length}`);
  console.log(`Fully captured   : ${captured}`);
  console.log(`Failed           : ${failed}`);
  console.log(`\nRef screenshots  : ${REF_DIR}/`);
  console.log(`SB screenshots   : ${SB_DIR}/`);
}

main().catch(console.error);
