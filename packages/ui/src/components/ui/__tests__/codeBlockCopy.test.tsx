import * as React from "react"
import { act } from "react"
import { describe, expect, it, vi } from "vitest"

import { createUser, mockClipboard, render, screen } from "../../../test/testUtils"
import { CodeBlock, SyntaxKey, SyntaxString, SyntaxValue } from "../code-block"

function getCopyButtons() {
  return screen.getAllByRole("button", { name: "Copy" }) as HTMLButtonElement[]
}

describe("CodeBlock copy behavior (RUN-966)", () => {
  it("copies the clicked block's tokenized code content", async () => {
    const user = createUser()
    const { writeText } = mockClipboard()

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
    await user.click(secondButton)

    expect(writeText).toHaveBeenCalledTimes(1)
    expect(writeText).toHaveBeenLastCalledWith("name: beta\nmodel: gpt-5.4")
  })

  it("copies numbered string content without visual line numbers", async () => {
    const user = createUser()
    const { writeText } = mockClipboard()

    render(
      <CodeBlock language="yaml" numbered>
        {"first: one\nsecond: two"}
      </CodeBlock>
    )

    const [button] = getCopyButtons()
    await user.click(button)

    expect(writeText).toHaveBeenCalledWith("first: one\nsecond: two")
  })

  it("does not enter copied state when clipboard is unavailable", async () => {
    const user = createUser()
    mockClipboard({ available: false })

    render(
      <CodeBlock language="yaml">
        {"name: unavailable"}
      </CodeBlock>
    )

    const [button] = getCopyButtons()
    expect(button.textContent).toBe("⧉")

    await user.click(button)

    expect(button.textContent).toBe("⧉")
  })

  it("does not enter copied state when clipboard write rejects", async () => {
    const user = createUser()
    const { writeText } = mockClipboard({
      writeText: vi.fn<(_: string) => Promise<void>>().mockRejectedValue(new Error("denied")),
    })

    render(
      <CodeBlock language="yaml">
        {"name: rejected"}
      </CodeBlock>
    )

    const [button] = getCopyButtons()
    await user.click(button)

    expect(writeText).toHaveBeenCalledWith("name: rejected")
    expect(button.textContent).toBe("⧉")
  })

  it("refreshes the copied-state timer on repeated successful clicks", async () => {
    vi.useFakeTimers()

    const user = createUser({ advanceTimers: vi.advanceTimersByTimeAsync })
    mockClipboard()

    render(
      <CodeBlock language="yaml">
        {"name: repeated"}
      </CodeBlock>
    )

    const [button] = getCopyButtons()

    await user.click(button)
    expect(button.textContent).toBe("✓")

    await act(async () => {
      vi.advanceTimersByTime(1500)
    })

    await user.click(button)

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
