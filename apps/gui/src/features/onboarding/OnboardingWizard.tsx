import { useRef, useCallback, useState } from "react";
import { useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { ProviderSetup } from "@/components/provider/ProviderSetup";
import type { ProviderSetupRef, ProviderSetupState } from "@/components/provider/ProviderSetup";
import { useUpdateAppSettings } from "@/queries/settings";

const RUNSIGHT_LOGO = (
  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="12" cy="5" r="2.5" fill="#5E6AD2" />
    <circle cx="5" cy="17" r="2.5" fill="#5E6AD2" opacity="0.7" />
    <circle cx="19" cy="17" r="2.5" fill="#5E6AD2" opacity="0.7" />
    <circle cx="12" cy="13" r="1.5" fill="#5E6AD2" opacity="0.5" />
    <line x1="12" y1="7.5" x2="12" y2="11.5" stroke="#5E6AD2" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="10.8" y1="14" x2="6.5" y2="15.5" stroke="#5E6AD2" strokeWidth="1.5" strokeLinecap="round" opacity="0.6" />
    <line x1="13.2" y1="14" x2="17.5" y2="15.5" stroke="#5E6AD2" strokeWidth="1.5" strokeLinecap="round" opacity="0.6" />
  </svg>
);

export function Component() {
  const navigate = useNavigate();
  const updateAppSettings = useUpdateAppSettings();
  const setupRef = useRef<ProviderSetupRef>(null);
  const [state, setState] = useState<ProviderSetupState | null>(null);

  const handleComplete = useCallback(() => {
    updateAppSettings.mutate({ onboarding_completed: true });
    navigate("/", { replace: true });
  }, [updateAppSettings, navigate]);

  const handleSkip = useCallback(() => {
    updateAppSettings.mutate({ onboarding_completed: true });
    navigate("/", { replace: true });
  }, [updateAppSettings, navigate]);

  return (
    <div className="relative min-h-screen bg-[#0D0D12] text-[#EDEDF0]">
      <div
        className="fixed inset-0 pointer-events-none z-0"
        style={{
          backgroundImage: `
            radial-gradient(circle at 50% 50%, rgba(94,106,210,0.05) 0%, transparent 60%),
            linear-gradient(rgba(45,45,53,0.1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(45,45,53,0.1) 1px, transparent 1px)
          `,
          backgroundSize: "100% 100%, 40px 40px, 40px 40px",
        }}
      />

      <main className="relative z-10 min-h-screen flex flex-col items-center px-8 py-8">
        <div className="w-[560px] max-w-[90vw] bg-[#16161C] border border-[#2D2D35] rounded-lg p-8 mt-6">
          {/* Header */}
          <div className="text-center mb-6">
            <div className="flex items-center justify-center gap-2 mb-4">
              <div className="w-8 h-8 [&>svg]:w-full [&>svg]:h-full">{RUNSIGHT_LOGO}</div>
              <span className="text-[13px] font-semibold tracking-[0.08em] uppercase">RUNSIGHT</span>
            </div>
            <h1 className="text-[22px] font-semibold tracking-[-0.02em] mb-1">Welcome to Runsight</h1>
            <p className="text-[14px] text-[#9292A0]">Let&apos;s get you set up with your first AI provider</p>
          </div>

          <ProviderSetup
            ref={setupRef}
            onStateChange={setState}
            confirmAction={
              <Button className="h-9 px-4" onClick={handleComplete}>
                Complete Setup
              </Button>
            }
          />

          {/* Footer */}
          <div className="pt-6 mt-6 border-t border-[#2D2D35] flex items-center justify-between">
            <Button
              variant="outline"
              className="h-9 px-4 border-[#3F3F4A] bg-transparent hover:bg-[#22222A]"
              onClick={() => setupRef.current?.stepBack()}
              disabled={!state?.canStepBack}
            >
              Back
            </Button>
            <button
              type="button"
              className="text-[14px] text-[#9292A0] hover:text-[#EDEDF0] transition-colors bg-transparent border-none cursor-pointer"
              onClick={handleSkip}
            >
              Skip for now
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
