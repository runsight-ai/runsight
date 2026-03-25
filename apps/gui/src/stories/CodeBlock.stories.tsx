import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Data Display/CodeBlock",
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div className="code-block" style={{ maxWidth: "480px" }}>
      <pre>{`name: customer-support-triage\nmodel: claude-sonnet-4-6\nsteps:\n  - id: classify\n    soul: classifier`}</pre>
    </div>
  ),
};

export const YAMLWithSyntax: Story = {
  name: "YAML with Syntax",
  render: () => (
    <div className="code-block" style={{ maxWidth: "480px" }}>
      <pre>
        <span className="token-key">name</span>{": "}
        <span className="token-string">"customer-support-triage"</span>{"\n"}
        <span className="token-key">model</span>{": "}
        <span className="token-value">claude-sonnet-4-6</span>{"\n"}
        <span className="token-key">steps</span>:{"\n"}
        {"  - "}
        <span className="token-key">id</span>{": "}
        <span className="token-value">classify</span>{"\n"}
        {"    "}
        <span className="token-key">soul</span>{": "}
        <span className="token-string">"classifier"</span>
      </pre>
    </div>
  ),
};

export const WithCopyButton: Story = {
  name: "With Copy Button",
  render: () => (
    <div className="code-block" style={{ maxWidth: "480px", position: "relative" }}>
      <button className="code-block__copy btn btn--ghost btn--xs" style={{ opacity: 1 }}>Copy</button>
      <pre>{`# Runsight workflow definition\nname: my-workflow\nversion: "1.0"\nsteps:\n  - id: step-1\n    soul: my-soul`}</pre>
    </div>
  ),
};

export const JSON: Story = {
  name: "JSON",
  render: () => (
    <div className="code-block" style={{ maxWidth: "480px" }}>
      <pre>{`{\n  "run_id": "run_8f3k2m",\n  "status": "running",\n  "tokens": 4820\n}`}</pre>
    </div>
  ),
};

export const InlineCode: Story = {
  name: "Inline Code",
  render: () => (
    <p style={{ fontSize: "var(--font-size-md)", color: "var(--text-primary)" }}>
      Use the <code className="code-inline">run()</code> method to execute a workflow. Pass <code className="code-inline">{"{ input: string }"}</code> as the argument.
    </p>
  ),
};
