import { describe, it, expect } from "vitest";
import { getStepTypeColor, getStatusColor, mapRunStatusToVariant } from "../colors";
import type { StatusVariant } from "@/components/shared";

// ---------------------------------------------------------------------------
// getStepTypeColor
// ---------------------------------------------------------------------------
describe("getStepTypeColor", () => {
  it("returns success colors for python", () => {
    expect(getStepTypeColor("python")).toBe(
      "bg-[var(--success-12)] text-[var(--success-9)]"
    );
  });

  it("returns warning colors for javascript", () => {
    expect(getStepTypeColor("javascript")).toBe(
      "bg-[var(--warning-12)] text-[var(--warning-9)]"
    );
  });

  it("returns elevated surface colors for shell", () => {
    expect(getStepTypeColor("shell")).toBe(
      "bg-[var(--surface-raised)] text-[var(--muted-foreground)]"
    );
  });

  it("returns running colors for http", () => {
    expect(getStepTypeColor("http")).toBe(
      "bg-[var(--running-12)] text-[var(--info-9)]"
    );
  });

  it("returns primary colors for prompt", () => {
    expect(getStepTypeColor("prompt")).toBe(
      "bg-[var(--accent-3)] text-[var(--interactive-default)]"
    );
  });

  it("returns error colors for condition", () => {
    expect(getStepTypeColor("condition")).toBe(
      "bg-[var(--error-12)] text-[var(--danger-9)]"
    );
  });

  it("returns accent-alt colors for loop", () => {
    expect(getStepTypeColor("loop")).toBe(
      "bg-[var(--accent-alt-12)] text-[var(--accent-alt)]"
    );
  });

  it("returns muted colors for unknown type", () => {
    expect(getStepTypeColor("unknown")).toBe(
      "bg-[var(--muted-12)] text-[var(--muted-foreground)]"
    );
  });

  it("is case-insensitive", () => {
    expect(getStepTypeColor("Python")).toBe(getStepTypeColor("python"));
    expect(getStepTypeColor("JAVASCRIPT")).toBe(getStepTypeColor("javascript"));
    expect(getStepTypeColor("HTTP")).toBe(getStepTypeColor("http"));
  });
});

// ---------------------------------------------------------------------------
// getStatusColor
// ---------------------------------------------------------------------------
describe("getStatusColor", () => {
  it("returns success color classes for completed", () => {
    const result = getStatusColor("completed");
    expect(result).toContain("success");
  });

  it("returns error color classes for failed", () => {
    const result = getStatusColor("failed");
    expect(result).toContain("error");
  });

  it("returns running color classes for running", () => {
    const result = getStatusColor("running");
    expect(result).toContain("running");
  });

  it("returns muted color classes for pending", () => {
    const result = getStatusColor("pending");
    expect(result).toContain("muted");
  });

  it("returns muted/default color classes for idle", () => {
    const result = getStatusColor("idle");
    expect(result).toContain("muted");
  });

  it("returns a fallback for unknown status", () => {
    const result = getStatusColor("some-random-status");
    expect(result).toBeTruthy();
    expect(typeof result).toBe("string");
  });
});

// ---------------------------------------------------------------------------
// mapRunStatusToVariant
// ---------------------------------------------------------------------------
describe("mapRunStatusToVariant", () => {
  it("maps 'completed' to 'success' variant", () => {
    const result: StatusVariant = mapRunStatusToVariant("completed");
    expect(result).toBe("success");
  });

  it("maps 'success' to 'success' variant", () => {
    const result: StatusVariant = mapRunStatusToVariant("success");
    expect(result).toBe("success");
  });

  it("maps 'failed' to 'error' variant", () => {
    const result: StatusVariant = mapRunStatusToVariant("failed");
    expect(result).toBe("error");
  });

  it("maps 'running' to 'running' variant", () => {
    const result: StatusVariant = mapRunStatusToVariant("running");
    expect(result).toBe("running");
  });

  it("maps 'pending' to 'pending' variant", () => {
    const result: StatusVariant = mapRunStatusToVariant("pending");
    expect(result).toBe("pending");
  });

  it("maps 'idle' to 'pending' variant", () => {
    const result: StatusVariant = mapRunStatusToVariant("idle");
    expect(result).toBe("pending");
  });

  it("maps unknown status to 'pending' variant as fallback", () => {
    const result: StatusVariant = mapRunStatusToVariant("something-else");
    expect(result).toBe("pending");
  });

  it("maps 'killed' to 'error' variant", () => {
    const result: StatusVariant = mapRunStatusToVariant("killed");
    expect(result).toBe("error");
  });

  it("maps 'paused' to 'warning' variant", () => {
    const result: StatusVariant = mapRunStatusToVariant("paused");
    expect(result).toBe("warning");
  });

  it("maps 'cancelled' to 'cancelled' variant", () => {
    const result: StatusVariant = mapRunStatusToVariant("cancelled");
    expect(result).toBe("cancelled");
  });
});
