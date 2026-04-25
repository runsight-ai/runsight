import { vi } from "vitest";

let restoreClipboard: (() => void) | null = null;

export function mockClipboard(options?: {
  available?: boolean;
  writeText?: ReturnType<typeof vi.fn<(_: string) => Promise<void>>>;
}) {
  restoreClipboard?.();

  const descriptor = Object.getOwnPropertyDescriptor(window.navigator, "clipboard");
  const writeText =
    options?.writeText ??
    vi.fn<(_: string) => Promise<void>>().mockResolvedValue(undefined);

  Object.defineProperty(window.navigator, "clipboard", {
    configurable: true,
    value: options?.available === false ? undefined : { writeText },
  });

  restoreClipboard = () => {
    if (descriptor) {
      Object.defineProperty(window.navigator, "clipboard", descriptor);
      return;
    }

    Reflect.deleteProperty(window.navigator, "clipboard");
  };

  return { writeText };
}

export function cleanupClipboardMocks() {
  restoreClipboard?.();
  restoreClipboard = null;
}
