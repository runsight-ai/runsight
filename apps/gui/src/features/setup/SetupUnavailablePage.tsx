import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router";
import { Button } from "@runsight/ui/button";
import { queryKeys } from "@/queries/keys";

export function Component() {
  const [isRetrying, setIsRetrying] = useState(false);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const retryTo = searchParams.get("retryTo") || "/";

  async function handleRetry() {
    setIsRetrying(true);
    await queryClient.invalidateQueries({ queryKey: queryKeys.settings.appSettings });
    navigate(retryTo, { replace: true });
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface-primary px-4 py-12">
      <div className="w-full max-w-[540px] rounded-xl border border-border-default bg-surface-secondary p-8 text-center shadow-sm">
        <div className="flex flex-col gap-3">
          <h1 className="text-3xl font-semibold tracking-tight text-heading">
            We could not verify your setup status
          </h1>
          <p className="text-sm leading-6 text-secondary">
            Runsight is keeping you out of protected screens until app settings can be loaded
            safely. Please try again to continue.
          </p>
        </div>

        <div className="mt-6 flex justify-center">
          <Button
            variant="primary"
            size="lg"
            onClick={handleRetry}
            disabled={isRetrying}
            loading={isRetrying}
          >
            {isRetrying ? "Retrying..." : "Retry"}
          </Button>
        </div>
      </div>
    </main>
  );
}
