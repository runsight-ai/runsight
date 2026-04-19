// @vitest-environment jsdom

import React from "react";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const SURFACE_DIR = resolve(__dirname, "..");
const FORM_SOURCE_PATH = resolve(SURFACE_DIR, "WorkflowInputsForm.tsx");
const FORM_IMPORT_PATH = "../WorkflowInputsForm";

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

function loadWorkflowInputsForm() {
  return import(FORM_IMPORT_PATH).then((mod) => mod.WorkflowInputsForm ?? mod.default);
}

async function renderWorkflowInputsForm(overrides: Record<string, unknown> = {}) {
  const WorkflowInputsForm = await loadWorkflowInputsForm();

  return render(
    React.createElement(WorkflowInputsForm, {
      schema,
      values: currentValues,
      errors: {},
      disabled: false,
      submitting: false,
      onChange: vi.fn(),
      ...overrides,
    }),
  );
}

function getBooleanControl(name: string) {
  return (
    screen.queryByRole("switch", { name }) ??
    screen.getByRole("checkbox", { name })
  );
}

function isBooleanControlOn(control: HTMLElement) {
  if (control instanceof HTMLInputElement) {
    return control.checked;
  }

  return control.getAttribute("aria-checked") === "true";
}

describe("RUN-902 WorkflowInputsForm", () => {
  it("renders string, number, boolean, json, and array inputs with accessible labels and the right control surfaces", async () => {
    await renderWorkflowInputsForm();

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

  it("shows the current values provided by the parent, including pretty JSON and array text", async () => {
    await renderWorkflowInputsForm();

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

  it("emits declared input names and typed values when the user edits a field", async () => {
    const onChange = vi.fn();
    await renderWorkflowInputsForm({ onChange, values: { ...currentValues } });

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

  it("marks required fields, exposes descriptions, and wires inline errors through aria-describedby", async () => {
    await renderWorkflowInputsForm({
      errors: { query: "Query is required." },
    });

    const query = screen.getByRole("textbox", { name: "Query" });
    const error = screen.getByText("Query is required.");

    expect(screen.getByText(/\*/)).toBeVisible();
    expect(query).toHaveAttribute("aria-required", "true");
    expect(query).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Search term shown to direct-run users.")).toBeVisible();
    expect(error).toBeVisible();
    expect(query).toHaveAttribute("aria-describedby", expect.stringContaining(error.id));
  });

  it("does not surface legacy workflow path language or mapping internals to direct-run users", async () => {
    const { container } = await renderWorkflowInputsForm();
    const text = container.textContent ?? "";

    expect(text).not.toMatch(/workflow\.[A-Za-z0-9_]+/);
    expect(text).not.toMatch(/\bmapping\b/i);
    expect(text).not.toMatch(/\btarget\b/i);
    expect(text).not.toMatch(/child internals/i);
  });

  it("keeps the component out of global canvas and run-input-schema stores", () => {
    expect(existsSync(FORM_SOURCE_PATH)).toBe(true);

    const source = readFileSync(FORM_SOURCE_PATH, "utf-8");

    expect(source).not.toMatch(/\buseCanvasStore\b/);
    expect(source).not.toMatch(/\buseRunInputSchemaDecision\b/);
  });
});
