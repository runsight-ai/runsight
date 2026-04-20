// @vitest-environment jsdom

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WorkflowInputsForm } from "../WorkflowInputsForm";

const schema = {
  query: {
    type: "string",
    required: true,
    default: null,
    description: "Search term shown to direct-run users.",
    sensitive: false,
  },
  retries: {
    type: "number",
    required: false,
    default: 3,
    description: "Retry budget for the current run.",
    sensitive: false,
  },
  enabled: {
    type: "boolean",
    required: false,
    default: false,
    description: "Whether this path is active.",
    sensitive: false,
  },
  config: {
    type: "json",
    required: false,
    default: null,
    description: "Structured runtime settings.",
    sensitive: false,
  },
  tags: {
    type: "array",
    required: false,
    default: null,
    description: "Ordered tags for the run.",
    sensitive: false,
  },
} as const;

const currentValues = {
  query: "alpha",
  retries: 7,
  enabled: true,
  config: { mode: "fast", nested: { size: 2 } },
  tags: ["one", "two"],
};

function getBooleanControl(name: string) {
  return screen.queryByRole("switch", { name }) ?? screen.getByRole("checkbox", { name });
}

function isBooleanControlOn(control: HTMLElement) {
  if (control instanceof HTMLInputElement) {
    return control.checked;
  }

  return control.getAttribute("aria-checked") === "true";
}

describe("RUN-902 WorkflowInputsForm", () => {
  it("renders string, number, boolean, json, and array inputs with accessible labels and the right control surfaces", () => {
    render(
      <WorkflowInputsForm
        schema={schema}
        values={currentValues}
        errors={{}}
        disabled={false}
        submitting={false}
        onChange={vi.fn()}
      />,
    );

    const query = screen.getByRole("textbox", { name: "Query" });
    const retries = screen.getByRole("spinbutton", { name: "Retries" });
    const enabled = getBooleanControl("Enabled");
    const config = screen.getByRole("textbox", { name: "Config" });
    const tags = screen.getByRole("textbox", { name: "Tags" });

    expect(query).toBeInstanceOf(HTMLInputElement);
    expect(query).toHaveAttribute("type", "text");
    expect(retries).toBeInstanceOf(HTMLInputElement);
    expect(retries).toHaveAttribute("type", "number");
    expect(enabled).toBeTruthy();
    expect(config).toBeInstanceOf(HTMLTextAreaElement);
    expect(tags).toBeInstanceOf(HTMLTextAreaElement);
  });

  it("shows the current values provided by the parent, including pretty JSON and array text", () => {
    render(
      <WorkflowInputsForm
        schema={schema}
        values={currentValues}
        errors={{}}
        disabled={false}
        submitting={false}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("textbox", { name: "Query" })).toHaveValue("alpha");
    expect(screen.getByRole("spinbutton", { name: "Retries" })).toHaveValue(7);
    expect(isBooleanControlOn(getBooleanControl("Enabled"))).toBe(true);
    expect(screen.getByRole("textbox", { name: "Config" })).toHaveValue(
      JSON.stringify(currentValues.config, null, 2),
    );
    expect(screen.getByRole("textbox", { name: "Tags" })).toHaveValue(
      JSON.stringify(currentValues.tags, null, 2),
    );
  });

  it("falls back to schema defaults when the parent omits values", () => {
    render(
      <WorkflowInputsForm
        schema={schema}
        values={{}}
        errors={{}}
        disabled={false}
        submitting={false}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("textbox", { name: "Query" })).toHaveValue("");
    expect(screen.getByRole("spinbutton", { name: "Retries" })).toHaveValue(3);
    expect(isBooleanControlOn(getBooleanControl("Enabled"))).toBe(false);
    expect(screen.getByRole("textbox", { name: "Config" })).toHaveValue("null");
    expect(screen.getByRole("textbox", { name: "Tags" })).toHaveValue("null");
  });

  it("emits declared input names and typed values when the user edits a field", () => {
    const onChange = vi.fn();

    render(
      <WorkflowInputsForm
        schema={schema}
        values={{ ...currentValues }}
        errors={{}}
        disabled={false}
        submitting={false}
        onChange={onChange}
      />,
    );

    fireEvent.change(screen.getByRole("textbox", { name: "Query" }), {
      target: { value: "beta" },
    });
    fireEvent.change(screen.getByRole("spinbutton", { name: "Retries" }), {
      target: { value: "42" },
    });
    fireEvent.click(getBooleanControl("Enabled"));
    fireEvent.change(screen.getByRole("textbox", { name: "Config" }), {
      target: { value: JSON.stringify({ mode: "slow", retry: 2 }) },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Tags" }), {
      target: { value: JSON.stringify(["x", "y"]) },
    });

    expect(onChange).toHaveBeenCalledWith("query", "beta");
    expect(onChange).toHaveBeenCalledWith("retries", 42);
    expect(onChange).toHaveBeenCalledWith("enabled", false);
    expect(onChange).toHaveBeenCalledWith("config", { mode: "slow", retry: 2 });
    expect(onChange).toHaveBeenCalledWith("tags", ["x", "y"]);
  });

  it("marks required fields, exposes descriptions, and wires inline errors through aria-describedby", () => {
    render(
      <WorkflowInputsForm
        schema={schema}
        values={currentValues}
        errors={{ query: "Query is required." }}
        disabled={false}
        submitting={false}
        onChange={vi.fn()}
      />,
    );

    const query = screen.getByRole("textbox", { name: "Query" });
    const error = screen.getByText("Query is required.");

    expect(screen.getByText(/\*/)).toBeTruthy();
    expect(query).toHaveAttribute("aria-required", "true");
    expect(query).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Search term shown to direct-run users.")).toBeTruthy();
    expect(error).toBeTruthy();
    expect(query.getAttribute("aria-describedby")).toContain(error.id);
  });

  it("does not surface legacy workflow path syntax or mapping internals to direct-run users", () => {
    render(
      <WorkflowInputsForm
        schema={schema}
        values={currentValues}
        errors={{}}
        disabled={false}
        submitting={false}
        onChange={vi.fn()}
      />,
    );

    const descriptions = [
      screen.getByText("Search term shown to direct-run users.").textContent ?? "",
      screen.getByText("Retry budget for the current run.").textContent ?? "",
      screen.getByText("Whether this path is active.").textContent ?? "",
      screen.getByText("Structured runtime settings.").textContent ?? "",
      screen.getByText("Ordered tags for the run.").textContent ?? "",
    ].join("\n");

    expect(descriptions).not.toMatch(/workflow\.[A-Za-z0-9_]+/);
    expect(descriptions).not.toMatch(/\bpath\s*:\s*target\b/i);
    expect(descriptions).not.toMatch(/\btarget\s*:\s*path\b/i);
    expect(descriptions).not.toMatch(/child internals/i);
  });

  it("does not render run controls, rerun affordances, modal chrome, or redaction copy", () => {
    const { container } = render(
      <WorkflowInputsForm
        schema={schema}
        values={currentValues}
        errors={{}}
        disabled={false}
        submitting={false}
        onChange={vi.fn()}
      />,
    );

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByRole("button", { name: /run/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /rerun/i })).toBeNull();

    const renderedText = container.textContent ?? "";

    expect(renderedText).not.toMatch(/\b(redact|redaction|secret|hidden copy|sensitive)\b/i);
  });
});
