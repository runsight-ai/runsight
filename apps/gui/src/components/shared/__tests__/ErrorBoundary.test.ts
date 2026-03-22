/**
 * RED-TEAM tests for RUN-239: Error Boundary Strategy.
 *
 * The app must have React Error Boundaries at three levels — App, Route, and
 * Canvas — so that a component crash never blanks the entire page. Currently
 * zero error boundaries exist.
 *
 * These tests MUST FAIL until the Green Team implements:
 *  - ErrorBoundary.tsx exporting AppErrorBoundary, RouteErrorBoundary,
 *    CanvasErrorBoundary as class components
 *  - Each class: getDerivedStateFromError, componentDidCatch, render, and a
 *    state-reset mechanism
 *
 * Environment: Vitest + Node (no DOM). Tests verify the class interface only.
 */

import { describe, it, expect } from "vitest";
import {
  AppErrorBoundary,
  RouteErrorBoundary,
  CanvasErrorBoundary,
} from "../ErrorBoundary";

// ---------------------------------------------------------------------------
// 1. Module exports exist (AC5 — tests verify error catching and fallback)
// ---------------------------------------------------------------------------

describe("ErrorBoundary module exports", () => {
  it("exports AppErrorBoundary", () => {
    expect(AppErrorBoundary).toBeDefined();
  });

  it("exports RouteErrorBoundary", () => {
    expect(RouteErrorBoundary).toBeDefined();
  });

  it("exports CanvasErrorBoundary", () => {
    expect(CanvasErrorBoundary).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// 2. Each boundary is a distinct class (AC1-2 — distinct fallback UI per level)
// ---------------------------------------------------------------------------

describe("Error boundaries are distinct classes", () => {
  it("AppErrorBoundary is not the same class as RouteErrorBoundary", () => {
    expect(AppErrorBoundary).not.toBe(RouteErrorBoundary);
  });

  it("AppErrorBoundary is not the same class as CanvasErrorBoundary", () => {
    expect(AppErrorBoundary).not.toBe(CanvasErrorBoundary);
  });

  it("RouteErrorBoundary is not the same class as CanvasErrorBoundary", () => {
    expect(RouteErrorBoundary).not.toBe(CanvasErrorBoundary);
  });
});

// ---------------------------------------------------------------------------
// 3. Class component interface — getDerivedStateFromError (AC5)
//    Each boundary must derive { hasError: true } from any thrown error.
// ---------------------------------------------------------------------------

describe("getDerivedStateFromError", () => {
  it("AppErrorBoundary.getDerivedStateFromError is a function", () => {
    expect(AppErrorBoundary.getDerivedStateFromError).toBeTypeOf("function");
  });

  it("RouteErrorBoundary.getDerivedStateFromError is a function", () => {
    expect(RouteErrorBoundary.getDerivedStateFromError).toBeTypeOf("function");
  });

  it("CanvasErrorBoundary.getDerivedStateFromError is a function", () => {
    expect(CanvasErrorBoundary.getDerivedStateFromError).toBeTypeOf("function");
  });

  it("AppErrorBoundary.getDerivedStateFromError returns { hasError: true }", () => {
    const state = AppErrorBoundary.getDerivedStateFromError(new Error("boom"));
    expect(state).toEqual({ hasError: true });
  });

  it("RouteErrorBoundary.getDerivedStateFromError returns { hasError: true }", () => {
    const state = RouteErrorBoundary.getDerivedStateFromError(new Error("boom"));
    expect(state).toEqual({ hasError: true });
  });

  it("CanvasErrorBoundary.getDerivedStateFromError returns { hasError: true }", () => {
    const state = CanvasErrorBoundary.getDerivedStateFromError(new Error("boom"));
    expect(state).toEqual({ hasError: true });
  });
});

// ---------------------------------------------------------------------------
// 4. componentDidCatch exists (AC4 — logs to console)
// ---------------------------------------------------------------------------

describe("componentDidCatch", () => {
  it("AppErrorBoundary.prototype.componentDidCatch is a function", () => {
    expect(AppErrorBoundary.prototype.componentDidCatch).toBeTypeOf("function");
  });

  it("RouteErrorBoundary.prototype.componentDidCatch is a function", () => {
    expect(RouteErrorBoundary.prototype.componentDidCatch).toBeTypeOf("function");
  });

  it("CanvasErrorBoundary.prototype.componentDidCatch is a function", () => {
    expect(CanvasErrorBoundary.prototype.componentDidCatch).toBeTypeOf("function");
  });
});

// ---------------------------------------------------------------------------
// 5. render method exists (AC3 — fallback has Retry/Reload button)
// ---------------------------------------------------------------------------

describe("render method", () => {
  it("AppErrorBoundary.prototype.render is a function", () => {
    expect(AppErrorBoundary.prototype.render).toBeTypeOf("function");
  });

  it("RouteErrorBoundary.prototype.render is a function", () => {
    expect(RouteErrorBoundary.prototype.render).toBeTypeOf("function");
  });

  it("CanvasErrorBoundary.prototype.render is a function", () => {
    expect(CanvasErrorBoundary.prototype.render).toBeTypeOf("function");
  });
});

// ---------------------------------------------------------------------------
// 6. State reset mechanism (AC3 — Retry/Reload buttons reset error state)
//    Each boundary must expose a way to reset hasError back to false.
// ---------------------------------------------------------------------------

describe("state reset mechanism", () => {
  it("AppErrorBoundary.prototype.resetError is a function", () => {
    expect(AppErrorBoundary.prototype.resetError).toBeTypeOf("function");
  });

  it("RouteErrorBoundary.prototype.resetError is a function", () => {
    expect(RouteErrorBoundary.prototype.resetError).toBeTypeOf("function");
  });

  it("CanvasErrorBoundary.prototype.resetError is a function", () => {
    expect(CanvasErrorBoundary.prototype.resetError).toBeTypeOf("function");
  });
});
