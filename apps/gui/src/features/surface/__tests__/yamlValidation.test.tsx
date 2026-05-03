// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useYamlValidation } from "../useYamlValidation";

function createEditorHarness() {
  const model = { uri: "in-memory://workflow.yaml" };
  const setModelMarkers = vi.fn();
  const editor = {
    getModel: vi.fn(() => model),
  };
  const monaco = {
    editor: { setModelMarkers },
    MarkerSeverity: { Error: 8 },
  };

  return { editor, model, monaco, setModelMarkers };
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useYamlValidation", () => {
  it("clears Monaco markers and reports a valid state for valid YAML", () => {
    const onValidation = vi.fn();
    const harness = createEditorHarness();
    const { result } = renderHook(() => useYamlValidation(onValidation));

    act(() => {
      result.current.setEditorRefs(harness.editor, harness.monaco);
      result.current.validate("workflow:\n  name: Valid Flow\n");
      vi.advanceTimersByTime(500);
    });

    expect(harness.setModelMarkers).toHaveBeenCalledWith(
      harness.model,
      "yaml-validation",
      [],
    );
    expect(onValidation).toHaveBeenCalledWith({
      isValid: true,
      errorCount: 0,
      errors: [],
    });
  });

  it("sets a Monaco error marker and reports line-level validation details for invalid YAML", () => {
    const onValidation = vi.fn();
    const harness = createEditorHarness();
    const { result } = renderHook(() => useYamlValidation(onValidation));

    act(() => {
      result.current.setEditorRefs(harness.editor, harness.monaco);
      result.current.validate("workflow:\n  name: [broken\n");
      vi.advanceTimersByTime(500);
    });

    const marker = harness.setModelMarkers.mock.calls[0]?.[2]?.[0] as {
      severity?: number;
      message?: string;
      startLineNumber?: number;
    };

    expect(marker.severity).toBe(8);
    expect(marker.message).toBeTruthy();
    expect(marker.startLineNumber).toBeGreaterThanOrEqual(1);
    expect(onValidation).toHaveBeenCalledWith(
      expect.objectContaining({
        isValid: false,
        errorCount: 1,
        errors: [expect.objectContaining({ line: expect.any(Number) })],
      }),
    );
  });

  it("debounces validation and evaluates only the latest editor value", () => {
    const onValidation = vi.fn();
    const harness = createEditorHarness();
    const { result } = renderHook(() => useYamlValidation(onValidation));

    act(() => {
      result.current.setEditorRefs(harness.editor, harness.monaco);
      result.current.validate("workflow:\n  name: [broken\n");
      vi.advanceTimersByTime(250);
      result.current.validate("workflow:\n  name: Recovered\n");
      vi.advanceTimersByTime(499);
    });

    expect(harness.setModelMarkers).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(harness.setModelMarkers).toHaveBeenCalledTimes(1);
    expect(harness.setModelMarkers).toHaveBeenCalledWith(
      harness.model,
      "yaml-validation",
      [],
    );
    expect(onValidation).toHaveBeenCalledWith({
      isValid: true,
      errorCount: 0,
      errors: [],
    });
  });
});
