// @vitest-environment jsdom

import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";

const dialogHarness = vi.hoisted(() => ({
  onOpenChange: undefined as undefined | ((open: boolean) => void),
}));

vi.mock("@runsight/ui/dialog", () => ({
  Dialog: ({
    open,
    onOpenChange,
    children,
  }: {
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
    children?: React.ReactNode;
  }) => {
    dialogHarness.onOpenChange = onOpenChange;
    return open ? React.createElement(React.Fragment, null, children) : null;
  },
  DialogContent: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("div", { role: "dialog" }, children),
  DialogHeader: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("div", null, children),
  DialogTitle: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("h2", null, children),
  DialogBody: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("div", null, children),
  DialogFooter: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("div", null, children),
  DialogOverlay: () => null,
  DialogPortal: ({ children }: { children?: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
  DialogClose: ({
    render,
    children,
    ...props
  }: {
    render?: React.ReactElement;
    children?: React.ReactNode;
  }) => {
    const onClick = () => dialogHarness.onOpenChange?.(false);

    if (React.isValidElement(render)) {
      return React.cloneElement(
        render,
        {
          ...render.props,
          ...props,
          onClick,
        },
        children,
      );
    }

    return React.createElement("button", { type: "button", ...props, onClick }, children);
  },
  DialogTrigger: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("button", { type: "button" }, children),
}));

const { RunInputsModal } = await import("../RunInputsModal");

type WorkflowInputSchemaItem = {
  type: "string" | "number" | "boolean" | "json" | "array";
  required?: boolean | null;
  default?: unknown;
  description?: string | null;
  sensitive?: boolean | null;
};

const defaultWorkflow = {
  id: "wf-run-903-defaults",
  name: "Nightly Search",
  input_schema: {
    query: {
      type: "string",
      required: true,
      default: "alpha",
      description: "Search term for the run.",
      sensitive: false,
    },
    config: {
      type: "json",
      required: false,
      default: { mode: "fast", retries: 2 },
      description: "Structured settings.",
      sensitive: false,
    },
    tags: {
      type: "array",
      required: false,
      default: ["one", "two"],
      description: "Ordered tags.",
      sensitive: false,
    },
  } satisfies Record<string, WorkflowInputSchemaItem>,
} as const;

const requiredWorkflow = {
  ...defaultWorkflow,
  id: "wf-run-903-required",
  input_schema: {
    ...defaultWorkflow.input_schema,
    query: {
      ...defaultWorkflow.input_schema.query,
      default: null,
    },
  },
};

const rerunWorkflow = {
  ...defaultWorkflow,
  id: "wf-run-903-rerun",
};

const initialValues = {
  query: "prefilled rerun query",
  config: { mode: "slow", nested: { size: 2 } },
  tags: ["rerun", "ready"],
};

function renderModal({
  workflow = defaultWorkflow,
  initialValues: currentInitialValues,
  onSubmit = vi.fn(),
  onOpenChange = vi.fn(),
}: {
  workflow?: Record<string, unknown>;
  initialValues?: Record<string, unknown>;
  onSubmit?: (...args: any[]) => unknown;
  onOpenChange?: (...args: any[]) => unknown;
} = {}) {
  render(
    <RunInputsModal
      open
      workflow={workflow}
      initialValues={currentInitialValues}
      onOpenChange={onOpenChange}
      onSubmit={onSubmit}
    />,
  );

  return { onSubmit, onOpenChange };
}

function getFieldError(control: HTMLElement) {
  const describedBy = control.getAttribute("aria-describedby") ?? "";
  const errorId = describedBy
    .split(/\s+/)
    .map((item) => item.trim())
    .find((item) => item.endsWith("-error"));

  expect(errorId).toBeTruthy();

  const error = document.getElementById(errorId!);
  expect(error).toBeTruthy();
  expect(error?.textContent?.trim()).not.toBe("");

  return error!;
}

function getPrimaryAction() {
  return screen.getByRole("button", { name: /run|submit|launch/i });
}

function getCancelAction() {
  return screen.getByRole("button", { name: /cancel/i });
}

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;

  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });

  return { promise, resolve, reject };
}

beforeEach(() => {
  dialogHarness.onOpenChange = undefined;
});

describe("RUN-903 RunInputsModal", () => {
  it("prefills workflow defaults when the modal opens", () => {
    renderModal();

    expect(screen.getByRole("textbox", { name: "Query" })).toHaveValue("alpha");
    expect(screen.getByRole("textbox", { name: "Config" })).toHaveValue(
      JSON.stringify(defaultWorkflow.input_schema.config.default, null, 2),
    );
    expect(screen.getByRole("textbox", { name: "Tags" })).toHaveValue(
      JSON.stringify(defaultWorkflow.input_schema.tags.default, null, 2),
    );
  });

  it("prefills provided initial values and submits the edited rerun payload by declared input name", async () => {
    const onSubmit = vi.fn(() => Promise.resolve());
    const onOpenChange = vi.fn();

    renderModal({
      workflow: rerunWorkflow,
      initialValues,
      onSubmit,
      onOpenChange,
    });

    expect(screen.getByRole("textbox", { name: "Query" })).toHaveValue(
      initialValues.query,
    );
    expect(screen.getByRole("textbox", { name: "Config" })).toHaveValue(
      JSON.stringify(initialValues.config, null, 2),
    );
    expect(screen.getByRole("textbox", { name: "Tags" })).toHaveValue(
      JSON.stringify(initialValues.tags, null, 2),
    );

    fireEvent.change(screen.getByRole("textbox", { name: "Query" }), {
      target: { value: "edited rerun query" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Config" }), {
      target: { value: JSON.stringify({ mode: "balanced", retries: 4 }, null, 2) },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Tags" }), {
      target: { value: JSON.stringify(["rerun", "edited"], null, 2) },
    });

    expect(screen.getByRole("textbox", { name: "Query" })).toHaveValue("edited rerun query");
    expect(screen.getByRole("textbox", { name: "Config" })).toHaveValue(
      JSON.stringify({ mode: "balanced", retries: 4 }, null, 2),
    );
    expect(screen.getByRole("textbox", { name: "Tags" })).toHaveValue(
      JSON.stringify(["rerun", "edited"], null, 2),
    );

    fireEvent.click(getPrimaryAction());

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith({
      query: "edited rerun query",
      config: { mode: "balanced", retries: 4 },
      tags: ["rerun", "edited"],
    });
    expect(onOpenChange).not.toHaveBeenCalledWith(false);

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it("blocks submit when a required input is empty", async () => {
    const onSubmit = vi.fn();

    renderModal({
      workflow: requiredWorkflow,
      initialValues: { query: "" },
      onSubmit,
    });

    fireEvent.click(getPrimaryAction());

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("textbox", { name: "Query" })).toHaveAttribute("aria-invalid", "true");
    expect(getFieldError(screen.getByRole("textbox", { name: "Query" }))).toBeTruthy();
  });

  it("shows inline errors for invalid JSON and array editing and blocks submit", async () => {
    const onSubmit = vi.fn();

    renderModal({
      workflow: defaultWorkflow,
      onSubmit,
    });

    fireEvent.change(screen.getByRole("textbox", { name: "Config" }), {
      target: { value: "{ broken json" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Tags" }), {
      target: { value: "[\"alpha\",]" },
    });

    fireEvent.click(getPrimaryAction());

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("textbox", { name: "Config" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("textbox", { name: "Tags" })).toHaveAttribute("aria-invalid", "true");
    expect(getFieldError(screen.getByRole("textbox", { name: "Config" }))).toBeTruthy();
    expect(getFieldError(screen.getByRole("textbox", { name: "Tags" }))).toBeTruthy();
  });

  it("maps workflow input validation errors to the query field and keeps the modal open", async () => {
    const onSubmit = vi.fn().mockRejectedValue(
      new ApiError(422, "WORKFLOW_INPUT_VALIDATION_ERROR", "Workflow input validation failed", {
        kind: "workflow_input_validation",
        workflow_id: "wf-run-903-defaults",
        fields: [
          {
            field: "query",
            code: "required",
            message: "Input 'query' is required.",
            input_path: ["inputs", "query"],
            expected_type: "string",
            actual_type: null,
          },
        ],
      }),
    );
    const onOpenChange = vi.fn();

    renderModal({ onSubmit, onOpenChange });

    fireEvent.click(getPrimaryAction());

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("textbox", { name: "Query" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Input 'query' is required.")).toBeTruthy();
    expect(getFieldError(screen.getByRole("textbox", { name: "Query" }))).toBeTruthy();
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  it("shows a top alert for non-field submit errors and keeps the modal open", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new ApiError(500, "RUN_FAILED", "Gateway exploded"));
    const onOpenChange = vi.fn();

    renderModal({ onSubmit, onOpenChange });

    fireEvent.click(getPrimaryAction());

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("alert")).toHaveTextContent("Gateway exploded");
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  it("closes the modal on idle cancel without submitting", () => {
    const onSubmit = vi.fn();
    const onOpenChange = vi.fn();

    renderModal({ onSubmit, onOpenChange });

    fireEvent.click(getCancelAction());

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("keeps the modal open while submitting and ignores cancel and close requests until the promise settles", async () => {
    const deferred = createDeferred<void>();
    const onSubmit = vi.fn(() => deferred.promise);
    const onOpenChange = vi.fn();

    renderModal({ onSubmit, onOpenChange });

    fireEvent.click(getPrimaryAction());

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("dialog")).toBeTruthy();

    fireEvent.click(getCancelAction());
    dialogHarness.onOpenChange?.(false);

    expect(onOpenChange).not.toHaveBeenCalledWith(false);

    deferred.resolve();

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });
});
