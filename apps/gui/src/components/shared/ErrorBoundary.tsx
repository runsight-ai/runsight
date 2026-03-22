import React from "react";

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
        <div className="h-screen w-screen flex items-center justify-center bg-background">
          <div className="text-center space-y-4">
            <h1 className="text-xl font-semibold text-foreground">
              Something went wrong
            </h1>
            <p className="text-sm text-muted-foreground">
              An unexpected error occurred. Please reload the page.
            </p>
            <button
              className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium"
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

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="rounded-lg border border-border bg-card p-6 text-center space-y-4 max-w-md">
            <h2 className="text-lg font-semibold text-foreground">
              This page encountered an error
            </h2>
            <p className="text-sm text-muted-foreground">
              Something went wrong while rendering this page.
            </p>
            <div className="flex items-center justify-center gap-3">
              <a
                href="/"
                className="px-4 py-2 rounded-md border border-border bg-background text-sm font-medium text-foreground hover:bg-surface-elevated"
              >
                Go to Dashboard
              </a>
              <button
                className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium"
                onClick={() => this.resetError()}
              >
                Retry
              </button>
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
        <div className="h-full w-full flex items-center justify-center bg-background/50 rounded-lg border border-border">
          <div className="text-center space-y-3">
            <p className="text-sm font-medium text-foreground">
              Canvas failed to render
            </p>
            <button
              className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-medium"
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
