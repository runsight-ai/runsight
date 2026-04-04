import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";
import { Toaster } from "sonner";
import { router } from "@/routes";
import { queryClient } from "@/lib/queryClient";
import { AppErrorBoundary } from "@/components/shared/ErrorBoundary";
import "@runsight/ui/styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppErrorBoundary>
        <RouterProvider router={router} />
      </AppErrorBoundary>
      <Toaster richColors position="bottom-right" />
    </QueryClientProvider>
  </StrictMode>,
);
