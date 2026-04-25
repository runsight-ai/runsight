import type { ReactElement, ReactNode } from "react";
import { render as testingLibraryRender, type RenderOptions } from "@testing-library/react";

function TestProviders({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export function render(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">,
) {
  return testingLibraryRender(ui, { wrapper: TestProviders, ...options });
}

export * from "@testing-library/react";
