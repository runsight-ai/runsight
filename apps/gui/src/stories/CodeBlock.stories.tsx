import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { CodeBlock, SyntaxKey, SyntaxString, SyntaxValue } from "@/components/ui/code-block";

const meta: Meta<typeof CodeBlock> = {
  title: "Data Display/CodeBlock",
  component: CodeBlock,
  parameters: { layout: "padded" },
  argTypes: {
    language: {
      control: { type: "text" },
      description: "Optional language label shown in the header bar",
    },
    numbered: {
      control: { type: "boolean" },
      description: "Whether to show line numbers",
    },
    showCopy: {
      control: { type: "boolean" },
      description: "Whether to show the copy-to-clipboard button",
    },
    children: {
      control: { type: "text" },
      description: "Code content to display",
    },
  },
};
export default meta;

type Story = StoryObj<typeof CodeBlock>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    language: "yaml",
    numbered: false,
    showCopy: true,
    children: `name: customer-support-triage\nmodel: claude-sonnet-4-6\nsteps:\n  - id: classify\n    soul: classifier`,
  },
  render: (args) => (
    <div style={{ maxWidth: "480px" }}>
      <CodeBlock {...args} />
    </div>
  ),
};

export const YAML: Story = {
  name: "YAML",
  render: () => (
    <div style={{ maxWidth: "480px" }}>
      <CodeBlock language="yaml">
        <SyntaxKey>name</SyntaxKey>{": "}
        <SyntaxString>"customer-support-triage"</SyntaxString>{"\n"}
        <SyntaxKey>model</SyntaxKey>{": "}
        <SyntaxValue>claude-sonnet-4-6</SyntaxValue>{"\n"}
        <SyntaxKey>steps</SyntaxKey>:{"\n"}
        {"  - "}
        <SyntaxKey>id</SyntaxKey>{": "}
        <SyntaxValue>classify</SyntaxValue>{"\n"}
        {"    "}
        <SyntaxKey>soul</SyntaxKey>{": "}
        <SyntaxString>"classifier"</SyntaxString>
      </CodeBlock>
    </div>
  ),
};

export const Python: Story = {
  name: "Python",
  render: () => (
    <div style={{ maxWidth: "480px" }}>
      <CodeBlock language="python">{`def run_workflow(name: str) -> dict:
    """Execute a Runsight workflow by name."""
    client = RunsightClient()
    result = client.run(name, input={"query": "hello"})
    return result.output`}</CodeBlock>
    </div>
  ),
};

export const WithLineNumbers: Story = {
  name: "With Line Numbers",
  render: () => (
    <div style={{ maxWidth: "480px" }}>
      <CodeBlock language="yaml" numbered showCopy={false}>{`name: customer-support-triage
model: claude-sonnet-4-6
steps:
  - id: classify
    soul: classifier
  - id: respond
    soul: responder
    depends_on: [classify]`}</CodeBlock>
    </div>
  ),
};

export const WithCopy: Story = {
  name: "With Copy",
  render: () => (
    <div style={{ maxWidth: "480px" }}>
      <CodeBlock language="json" showCopy>{`{
  "run_id": "run_8f3k2m",
  "status": "running",
  "tokens": 4820
}`}</CodeBlock>
    </div>
  ),
};
