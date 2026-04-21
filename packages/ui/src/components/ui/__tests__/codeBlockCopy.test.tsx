// @vitest-environment jsdom

import * as React from "react"
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { CodeBlock, SyntaxKey, SyntaxString, SyntaxValue } from "../code-block"

let container: HTMLDivElement
let root: Root | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true

function setClipboard(writeText?: (text: string) => Promise<void>) {
  Object.defineProperty(window.navigator, "clipboard", {
    configurable: true,
    value: writeText ? { writeText } : undefined,
  })
}

function render(element: React.ReactElement) {
  root = createRoot(container)

  act(() => {
    root?.render(element)
  })
}

function getCopyButtons() {
  return Array.from(container.querySelectorAll('button[aria-label="Copy"]')) as HTMLButtonElement[]
}

async function click(button: HTMLButtonElement) {
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
  })
}

beforeEach(() => {
  container = document.createElement("div")
  document.body.appendChild(container)
})

afterEach(() => {
  act(() => {
    root?.unmount()
  })

  root = null
  container.remove()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe("CodeBlock copy behavior (RUN-966)", () => {
  it("copies the clicked block's tokenized code content", async () => {
    const writeText = vi.fn<(_: string) => Promise<void>>().mockResolvedValue(undefined)
    setClipboard(writeText)

    render(
      <div>
        <CodeBlock language="yaml">
          <SyntaxKey>name</SyntaxKey>{": "}
          <SyntaxString>alpha</SyntaxString>{"\n"}
          <SyntaxKey>model</SyntaxKey>{": "}
          <SyntaxValue>gpt-4.1</SyntaxValue>
        </CodeBlock>
        <CodeBlock language="yaml">
          <SyntaxKey>name</SyntaxKey>{": "}
          <SyntaxString>beta</SyntaxString>{"\n"}
          <SyntaxKey>model</SyntaxKey>{": "}
          <SyntaxValue>gpt-5.4</SyntaxValue>
        </CodeBlock>
      </div>
    )

    const [, secondButton] = getCopyButtons()
    await click(secondButton)

    expect(writeText).toHaveBeenCalledTimes(1)
    expect(writeText).toHaveBeenLastCalledWith("name: beta\nmodel: gpt-5.4")
  })

  it("copies numbered string content without visual line numbers", async () => {
    const writeText = vi.fn<(_: string) => Promise<void>>().mockResolvedValue(undefined)
    setClipboard(writeText)

    render(
      <CodeBlock language="yaml" numbered>
        {"first: one\nsecond: two"}
      </CodeBlock>
    )

    const [button] = getCopyButtons()
    await click(button)

    expect(writeText).toHaveBeenCalledWith("first: one\nsecond: two")
  })

  it("does not enter copied state when clipboard is unavailable", async () => {
    setClipboard()

    render(
      <CodeBlock language="yaml">
        {"name: unavailable"}
      </CodeBlock>
    )

    const [button] = getCopyButtons()
    expect(button.textContent).toBe("⧉")

    await click(button)

    expect(button.textContent).toBe("⧉")
  })

  it("does not enter copied state when clipboard write rejects", async () => {
    const writeText = vi.fn<(_: string) => Promise<void>>().mockRejectedValue(new Error("denied"))
    setClipboard(writeText)

    render(
      <CodeBlock language="yaml">
        {"name: rejected"}
      </CodeBlock>
    )

    const [button] = getCopyButtons()
    await click(button)

    expect(writeText).toHaveBeenCalledWith("name: rejected")
    expect(button.textContent).toBe("⧉")
  })

  it("refreshes the copied-state timer on repeated successful clicks", async () => {
    vi.useFakeTimers()

    const writeText = vi.fn<(_: string) => Promise<void>>().mockResolvedValue(undefined)
    setClipboard(writeText)

    render(
      <CodeBlock language="yaml">
        {"name: repeated"}
      </CodeBlock>
    )

    const [button] = getCopyButtons()

    await click(button)
    expect(button.textContent).toBe("✓")

    await act(async () => {
      vi.advanceTimersByTime(1500)
    })

    await click(button)

    await act(async () => {
      vi.advanceTimersByTime(600)
    })

    expect(button.textContent).toBe("✓")

    await act(async () => {
      vi.advanceTimersByTime(1400)
    })

    expect(button.textContent).toBe("⧉")
  })
})
