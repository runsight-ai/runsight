import React from "react";
import { Button } from "@runsight/ui/button";

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

interface ErrorBoundaryState {
  hasError: boolean;
}

// ---------------------------------------------------------------------------
// AppErrorBoundary — wraps entire app
// ---------------------------------------------------------------------------

export class AppErrorBoundary extends React.Component<
  React.PropsWithChildren<Record<string, unknown>>,
  ErrorBoundaryState
> {
  constructor(props: React.PropsWithChildren<Record<string, unknown>>) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(_error: Error): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    console.error("[AppErrorBoundary]", error, errorInfo);
  }

  resetError(): void {
    this.setState({ hasError: false });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="h-screen w-screen flex items-center justify-center bg-surface-primary">
          <div className="text-center space-y-4">
            <h1 className="text-xl font-semibold text-primary">
              Something went wrong
            </h1>
            <p className="text-sm text-muted">
              An unexpected error occurred. Please reload the page.
            </p>
            <button
              className="px-4 py-2 rounded-md bg-interactive-default text-on-accent text-sm font-medium"
              onClick={() => window.location.reload()}
            >
              Reload
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// ---------------------------------------------------------------------------
// RouteErrorBoundary — wraps route content (Outlet)
// ---------------------------------------------------------------------------

export class RouteErrorBoundary extends React.Component<
  React.PropsWithChildren<Record<string, unknown>>,
  ErrorBoundaryState
> {
  constructor(props: React.PropsWithChildren<Record<string, unknown>>) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(_error: Error): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    console.error("[RouteErrorBoundary]", error, errorInfo);
  }

  resetError(): void {
    this.setState({ hasError: false });
  }

  retryRoute(): void {
    this.resetError();
    window.location.reload();
  }

  goToDashboard(): void {
    this.resetError();
    window.location.assign("/");
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="rounded-lg border border-border-default bg-surface-secondary p-6 text-center space-y-4 max-w-md">
            <h2 className="text-lg font-semibold text-primary">
              This page encountered an error
            </h2>
            <p className="text-sm text-muted">
              Something went wrong while rendering this page.
            </p>
            <div className="flex items-center justify-center gap-3">
              <Button
                type="button"
                variant="secondary"
                onClick={() => this.goToDashboard()}
              >
                Go to Dashboard
              </Button>
              <Button
                type="button"
                variant="primary"
                onClick={() => this.retryRoute()}
              >
                Retry
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// ---------------------------------------------------------------------------
// CanvasErrorBoundary — wraps ReactFlow instances
// ---------------------------------------------------------------------------

export class CanvasErrorBoundary extends React.Component<
  React.PropsWithChildren<Record<string, unknown>>,
  ErrorBoundaryState
> {
  constructor(props: React.PropsWithChildren<Record<string, unknown>>) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(_error: Error): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    console.error("[CanvasErrorBoundary]", error, errorInfo);
  }

  resetError(): void {
    this.setState({ hasError: false });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="h-full w-full flex items-center justify-center bg-surface-primary/50 rounded-lg border border-border-default">
          <div className="text-center space-y-3">
            <p className="text-sm font-medium text-primary">
              Canvas failed to render
            </p>
            <button
              className="px-3 py-1.5 rounded-md bg-interactive-default text-on-accent text-xs font-medium"
              onClick={() => this.resetError()}
            >
              Retry
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
