import { cleanup } from "@testing-library/react";
import { afterEach, expect } from "vitest";

expect.extend({
  toBeDisabled(received: Element) {
    const pass = received.hasAttribute("disabled");

    return {
      pass,
      message: () => `expected element ${pass ? "not " : ""}to be disabled`,
    };
  },
  toHaveAttribute(
    received: Element,
    name: string,
    expected?: string,
  ) {
    const actual = received.getAttribute(name);
    const pass = expected === undefined ? actual !== null : actual === expected;

    return {
      pass,
      message: () =>
        expected === undefined
          ? `expected element ${pass ? "not " : ""}to have attribute "${name}"`
          : `expected attribute "${name}" ${pass ? "not " : ""}to be "${expected}", received "${actual}"`,
    };
  },
});

const NativeRequest = globalThis.Request;
if (NativeRequest) {
  class RequestWithCompatibleSignal extends NativeRequest {
    constructor(input: RequestInfo | URL, init?: RequestInit) {
      if (init?.signal) {
        const { signal: _signal, ...rest } = init;
        init = rest;
      }

      super(input, init);
    }
  }

  Object.defineProperty(globalThis, "Request", {
    value: RequestWithCompatibleSignal,
    writable: true,
    configurable: true,
  });
}

afterEach(() => {
  cleanup();
});
