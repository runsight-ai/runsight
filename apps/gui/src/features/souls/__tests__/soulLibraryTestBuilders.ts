import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

export type SoulLibraryRow = Record<string, unknown>;

export type SoulLibraryQuery = {
  data: SoulLibraryRow[];
  isLoading: boolean;
  isError: boolean;
};

export function buildAvailableTools() {
  return [
    {
      id: "http",
      name: "HTTP Requests",
      description: "Fetch external APIs.",
      origin: "builtin",
      executor: "native",
    },
    {
      id: "request_lookup",
      name: "Request Lookup",
      description: "Fetch live report data.",
      origin: "custom",
      executor: "request",
    },
    {
      id: "python_helper",
      name: "Python Helper",
      description: "Run a local analysis helper.",
      origin: "custom",
      executor: "python",
    },
  ];
}

export function buildSoulsQuery(): SoulLibraryQuery {
  return {
    data: [
      {
        id: "soul_alpha",
        role: "Researcher",
        system_prompt: "You are a senior researcher.",
        model_name: "gpt-4o",
        provider: "openai",
        avatar_color: "info",
        tools: ["http", "request_lookup", "python_helper"],
        workflow_count: 10,
        modified_at: 1_775_000_000,
      },
      {
        id: "soul_beta",
        role: "Analyst",
        system_prompt: "",
        model_name: "claude-3-5-sonnet",
        provider: "anthropic",
        avatar_color: "success",
        tools: ["orphaned_tool"],
        workflow_count: 2,
        modified_at: 1_774_000_000,
      },
    ],
    isLoading: false,
    isError: false,
  };
}

export function renderSoulLibraryPage(SoulLibraryPage: unknown) {
  return renderToStaticMarkup(
    React.createElement(SoulLibraryPage as React.ComponentType<Record<string, unknown>>),
  );
}

export function renderColumnMarkup(node: React.ReactNode) {
  return renderToStaticMarkup(React.createElement(React.Fragment, null, node));
}
