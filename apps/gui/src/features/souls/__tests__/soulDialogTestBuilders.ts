import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

export type WorkflowUsage = {
  workflow_id: string;
  workflow_name: string;
};

export type SoulLike = {
  id: string;
  role: string;
  provider: string;
  model_name: string;
  system_prompt: string;
  tools: string[];
  temperature: number;
  max_tool_iterations: number;
  avatar_color: string;
};

export function makeSoul(overrides: Partial<SoulLike> = {}): SoulLike {
  return {
    id: "research_soul",
    role: "Researcher",
    provider: "openai",
    model_name: "gpt-4o",
    system_prompt: "You are a careful research assistant.",
    tools: ["browser"],
    temperature: 0.7,
    max_tool_iterations: 5,
    avatar_color: "accent",
    ...overrides,
  };
}

export function buildWorkflowUsages(count: 3 | 7 = 3): WorkflowUsage[] {
  const usages = [
    { workflow_id: "research_flow", workflow_name: "Research Flow" },
    { workflow_id: "review_flow", workflow_name: "Review Flow" },
    { workflow_id: "deploy_flow", workflow_name: "Deploy Flow" },
    { workflow_id: "qa_flow", workflow_name: "QA Flow" },
    { workflow_id: "publish_flow", workflow_name: "Publish Flow" },
    { workflow_id: "archive_flow", workflow_name: "Archive Flow" },
    { workflow_id: "audit_flow", workflow_name: "Audit Flow" },
  ];

  return usages.slice(0, count);
}

export function textContent(node: React.ReactNode): string {
  if (node == null || typeof node === "boolean") {
    return "";
  }

  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }

  if (!React.isValidElement(node)) {
    return "";
  }

  return React.Children.toArray(node.props.children).map(textContent).join("");
}

export function markup(node: React.ReactNode): string {
  return renderToStaticMarkup(React.createElement(React.Fragment, null, node));
}

export function findElement(
  node: React.ReactNode,
  predicate: (element: React.ReactElement) => boolean,
): React.ReactElement | undefined {
  if (!React.isValidElement(node)) {
    return undefined;
  }

  if (predicate(node)) {
    return node;
  }

  for (const child of React.Children.toArray(node.props.children)) {
    const match = findElement(child, predicate);
    if (match) {
      return match;
    }
  }

  return undefined;
}

export function findButton(
  node: React.ReactNode,
  label: string | RegExp,
): React.ReactElement | undefined {
  const matcher =
    typeof label === "string"
      ? (value: string) => value === label
      : (value: string) => label.test(value);

  return findElement(
    node,
    (element) => element.type === "button" && matcher(textContent(element)),
  );
}
