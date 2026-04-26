import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { cleanupClipboardMocks } from "./clipboard";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

afterEach(() => {
  cleanup();
  cleanupClipboardMocks();
  vi.restoreAllMocks();
  vi.useRealTimers();
});
