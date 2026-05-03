import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { cleanupClipboardMocks } from "./clipboard";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}

afterEach(() => {
  cleanup();
  cleanupClipboardMocks();
  vi.restoreAllMocks();
  vi.useRealTimers();
});
