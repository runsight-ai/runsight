/**
 * Playwright global setup — starts an isolated API server with a temp SQLite DB.
 * Ensures no pollution of the real database.
 */
import { type FullConfig } from "@playwright/test";
import { execSync, spawn, type ChildProcess } from "child_process";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import * as net from "net";

let apiProcess: ChildProcess | null = null;
let tmpDir: string | null = null;

function findFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, () => {
      const addr = server.address();
      if (addr && typeof addr === "object") {
        const port = addr.port;
        server.close(() => resolve(port));
      } else {
        reject(new Error("Failed to get port"));
      }
    });
  });
}

async function waitForServer(url: string, timeoutMs = 30000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      // not ready yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Server at ${url} did not start within ${timeoutMs}ms`);
}

async function globalSetup(config: FullConfig) {
  const useIntegration = process.env.E2E_INTEGRATION === "1";
  if (!useIntegration) return;

  tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "runsight-e2e-"));
  const dbPath = path.join(tmpDir, "test.db");
  const customDir = path.join(tmpDir, "custom");

  fs.mkdirSync(path.join(customDir, "workflows"), { recursive: true });
  fs.mkdirSync(path.join(customDir, "souls"), { recursive: true });
  fs.mkdirSync(path.join(customDir, "steps"), { recursive: true });
  fs.mkdirSync(path.join(customDir, "tasks"), { recursive: true });

  const apiPort = await findFreePort();
  const repoRoot = path.resolve(__dirname, "../../..");
  const apiDir = path.join(repoRoot, "apps/api");

  process.env.RUNSIGHT_API_PORT = String(apiPort);
  process.env.RUNSIGHT_TEST_TMP_DIR = tmpDir;

  apiProcess = spawn(
    "python",
    ["-m", "uvicorn", "runsight_api.main:app", "--host", "127.0.0.1", "--port", String(apiPort)],
    {
      cwd: path.join(apiDir, "src"),
      env: {
        ...process.env,
        RUNSIGHT_DB_URL: `sqlite:///${dbPath}`,
        RUNSIGHT_BASE_PATH: tmpDir,
        RUNSIGHT_DEBUG: "false",
        PYTHONPATH: path.join(apiDir, "src"),
      },
      stdio: ["ignore", "pipe", "pipe"],
    }
  );

  apiProcess.stdout?.on("data", (data: Buffer) => {
    if (process.env.DEBUG) process.stdout.write(`[API] ${data}`);
  });
  apiProcess.stderr?.on("data", (data: Buffer) => {
    if (process.env.DEBUG) process.stderr.write(`[API] ${data}`);
  });

  await waitForServer(`http://127.0.0.1:${apiPort}/health`);
  console.log(`[E2E Setup] API running on port ${apiPort}, DB: ${dbPath}`);
}

export default globalSetup;
