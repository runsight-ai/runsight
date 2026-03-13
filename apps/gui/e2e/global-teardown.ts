/**
 * Playwright global teardown — stops isolated API and cleans up temp DB.
 */
import * as fs from "fs";

async function globalTeardown() {
  const useIntegration = process.env.E2E_INTEGRATION === "1";
  if (!useIntegration) return;

  const tmpDir = process.env.RUNSIGHT_TEST_TMP_DIR;
  if (tmpDir && fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true, force: true });
    console.log(`[E2E Teardown] Cleaned up temp dir: ${tmpDir}`);
  }
}

export default globalTeardown;
