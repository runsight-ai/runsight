import type { ReactElement, ReactNode } from "react";
import {
  act,
  fireEvent,
  render as testingLibraryRender,
  type RenderOptions,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";

function TestProviders({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export function render(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">,
) {
  return testingLibraryRender(ui, { wrapper: TestProviders, ...options });
}

export function createUser(options?: {
  advanceTimers?: ((delay: number) => Promise<void> | void) | undefined;
}) {
  if (!options?.advanceTimers) {
    return userEvent.setup({
      delay: null,
    });
  }

  const advanceTimers = options.advanceTimers;

  return {
    async click(element: Element) {
      await act(async () => {
        fireEvent.click(element);
        await advanceTimers(0);
      });
    },
    async hover(element: Element) {
      await act(async () => {
        fireEvent.pointerOver(element);
        fireEvent.pointerEnter(element);
        fireEvent.mouseOver(element);
        fireEvent.mouseEnter(element);
        await advanceTimers(0);
      });
    },
    async unhover(element: Element) {
      await act(async () => {
        fireEvent.pointerOut(element);
        fireEvent.pointerLeave(element);
        fireEvent.mouseOut(element);
        fireEvent.mouseLeave(element);
        await advanceTimers(0);
      });
    },
  };
}

export { mockClipboard } from "./clipboard";
export * from "@testing-library/react";
