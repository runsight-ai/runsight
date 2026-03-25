import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import {
  CodeBlock,
  SyntaxKey,
  SyntaxString,
  SyntaxValue,
} from "@/components/ui/code-block"

const meta: Meta<typeof CodeBlock> = {
  title: "Data Display/CodeBlock",
  component: CodeBlock,
  parameters: {
    layout: "padded",
  },
  argTypes: {
    language: { control: "text" },
    numbered: { control: "boolean" },
    showCopy: { control: "boolean" },
  },
}

export default meta

type Story = StoryObj<typeof CodeBlock>

// ---------------------------------------------------------------------------
// Default — basic code block with plain text
// ---------------------------------------------------------------------------

export const Default: Story = {
  args: {
    language: "yaml",
    showCopy: true,
    children: `name: customer-support-triage\nmodel: claude-sonnet-4-6\nsteps:\n  - id: classify\n    soul: classifier`,
  },
}

// ---------------------------------------------------------------------------
// YAMLWithSyntax — YAML code block with syntax highlighting tokens
// ---------------------------------------------------------------------------

export const YAMLWithSyntax: Story = {
  name: "YAML with Syntax",
  render: () => (
    <CodeBlock language="yaml" showCopy>
      <SyntaxKey>name</SyntaxKey>:{" "}
      <SyntaxString>"customer-support-triage"</SyntaxString>
      {"\n"}
      <SyntaxKey>model</SyntaxKey>:{" "}
      <SyntaxValue>claude-sonnet-4-6</SyntaxValue>
      {"\n"}
      <SyntaxKey>steps</SyntaxKey>:{"\n"}
      {"  - "}
      <SyntaxKey>id</SyntaxKey>:{" "}
      <SyntaxValue>classify</SyntaxValue>
      {"\n"}
      {"    "}
      <SyntaxKey>soul</SyntaxKey>:{" "}
      <SyntaxString>"classifier"</SyntaxString>
    </CodeBlock>
  ),
}

// ---------------------------------------------------------------------------
// WithCopyButton — demonstrates the copy button interaction
// ---------------------------------------------------------------------------

export const WithCopyButton: Story = {
  name: "With Copy Button",
  render: () => (
    <CodeBlock language="yaml" showCopy>
      {`# Runsight workflow definition\nname: my-workflow\nversion: "1.0"\nsteps:\n  - id: step-1\n    soul: my-soul`}
    </CodeBlock>
  ),
}

// ---------------------------------------------------------------------------
// Clipboard — alias for copy button story (alternate keyword match)
// ---------------------------------------------------------------------------

export const Clipboard: Story = {
  name: "Clipboard Copy",
  render: () => (
    <CodeBlock language="json" showCopy>
      {`{\n  "run_id": "run_8f3k2m",\n  "status": "running",\n  "tokens": 4820\n}`}
    </CodeBlock>
  ),
}

// ---------------------------------------------------------------------------
// NoHeader — code block without language label or copy button
// ---------------------------------------------------------------------------

export const NoHeader: Story = {
  name: "No Header",
  args: {
    language: undefined,
    showCopy: false,
    children: `const result = await workflow.run({ input: "Hello" });`,
  },
}
