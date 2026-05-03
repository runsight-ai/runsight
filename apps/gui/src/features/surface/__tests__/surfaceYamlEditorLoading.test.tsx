// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

const harness = vi.hoisted(() => ({
  workflowYaml: "workflow:\n  name: Loaded From Workflow\n",
  setYamlContent: vi.fn(),
  markSaved: vi.fn(),
  setEditorRefs: vi.fn(),
  validate: vi.fn(),
  editorProps: [] as Array<{
    value?: string;
    options?: { readOnly?: boolean };
    onChange?: (value: string | undefined) => void;
    onMount?: (editor: unknown, monaco: unknown) => void;
    beforeMount?: (monaco: unknown) => void;
  }>,
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflow: () => ({
    data: { yaml: harness.workflowYaml },
  }),
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: Object.assign(
    () => ({
      setYamlContent: harness.setYamlContent,
      markSaved: harness.markSaved,
    }),
    {
      getState: () => ({
        setYamlContent: harness.setYamlContent,
        markSaved: harness.markSaved,
      }),
    },
  ),
}));

vi.mock("../useYamlValidation", () => ({
  useYamlValidation: () => ({
    validate: harness.validate,
    setEditorRefs: harness.setEditorRefs,
  }),
}));

vi.mock("../yamlTheme", () => ({
  defineYamlTheme: vi.fn(),
}));

vi.mock("@monaco-editor/react", () => ({
  default: (props: {
    value?: string;
    options?: { readOnly?: boolean };
    onChange?: (value: string | undefined) => void;
    onMount?: (editor: unknown, monaco: unknown) => void;
    beforeMount?: (monaco: unknown) => void;
  }) => {
    harness.editorProps.push(props);
    props.beforeMount?.({});
    props.onMount?.({ getModel: () => null }, {});
    return (
      <textarea
        aria-label="Workflow YAML editor"
        readOnly={Boolean(props.options?.readOnly)}
        value={props.value ?? ""}
        onChange={(event) => props.onChange?.(event.currentTarget.value)}
      />
    );
  },
}));

import { SurfaceYamlEditor } from "../SurfaceYamlEditor";

beforeEach(() => {
  harness.workflowYaml = "workflow:\n  name: Loaded From Workflow\n";
  harness.setYamlContent.mockReset();
  harness.markSaved.mockReset();
  harness.setEditorRefs.mockReset();
  harness.validate.mockReset();
  harness.editorProps = [];
});

afterEach(() => {
  cleanup();
});

describe("SurfaceYamlEditor loading behavior", () => {
  it("shows a loading fallback before the editor module resolves", async () => {
    render(<SurfaceYamlEditor workflowId="wf_editor" />);

    expect(screen.getByText("Loading editor...")).toBeTruthy();
    expect(await screen.findByLabelText("Workflow YAML editor")).toBeTruthy();
  });

  it("loads workflow YAML into the editor and canvas store", async () => {
    render(<SurfaceYamlEditor workflowId="wf_editor" />);

    const editor = await screen.findByLabelText("Workflow YAML editor");
    expect((editor as HTMLTextAreaElement).value).toBe(harness.workflowYaml);

    await waitFor(() => {
      expect(harness.setYamlContent).toHaveBeenCalledWith(harness.workflowYaml);
      expect(harness.markSaved).toHaveBeenCalled();
    });
  });

  it("renders provided readonly YAML without fetching mutable editor state", async () => {
    render(
      <SurfaceYamlEditor
        workflowId="wf_editor"
        yaml="workflow:\n  name: Historical Snapshot\n"
        readOnly
      />,
    );

    const editor = await screen.findByLabelText("Workflow YAML editor");
    expect((editor as HTMLTextAreaElement).readOnly).toBe(true);
    expect((editor as HTMLTextAreaElement).value).toContain("Historical Snapshot");
    expect(harness.editorProps.at(-1)?.options?.readOnly).toBe(true);
  });
});
