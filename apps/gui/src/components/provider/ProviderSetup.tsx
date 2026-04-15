export type { ProviderDef, TestStatus, ProviderSetupState, ProviderSetupRef, EditingProvider } from "./types";
export { HERO_PROVIDERS, DROPDOWN_PROVIDERS, ALL_PROVIDERS } from "./constants";
import { useEffect, useRef, useCallback, useImperativeHandle, forwardRef } from "react";
import type { ReactNode } from "react";
import { Input } from "@runsight/ui/input";
import { Label } from "@runsight/ui/label";
import { Switch } from "@runsight/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@runsight/ui/select";
import { Check, Loader2, XCircle, Eye, EyeOff } from "lucide-react";
import { useProviderSetupForm } from "./hooks/useProviderSetupForm";
import { useProviderConnection } from "./hooks/useProviderConnection";
import { HERO_PROVIDERS, DROPDOWN_PROVIDERS } from "./constants";
import type { EditingProvider, ProviderSetupRef, ProviderSetupState } from "./types";
export const ProviderSetup = forwardRef<ProviderSetupRef, { onStateChange?: (s: ProviderSetupState) => void; confirmAction?: ReactNode; autoTest?: boolean; autoTestDelay?: number; editing?: EditingProvider }>(
  function ProviderSetup({ onStateChange, confirmAction, autoTest = true, autoTestDelay = 1200, editing }, ref) {
    const isEditMode = !!editing;
    const form = useProviderSetupForm(editing);
    const { selectedProviderId, dropdownValue, displayName, apiKey, showApiKey, useEnvVar, envVarName, baseUrl, provider, isOllama, step1Done, setDisplayName, setApiKey, setShowApiKey, setUseEnvVar, setEnvVarName, setBaseUrl, selectProvider, fullReset } = form;
    const conn = useProviderConnection({ provider, apiKey, baseUrl, displayName, isOllama, isEditMode, editing, useEnvVar, envVarName });
    const { testStatus, testMessage, createdProviderIdRef, runTest, resetTestState } = conn;
    const step2Done = testStatus === "success";
    const canStepBack = isEditMode ? false : step1Done;
    const stepBack = useCallback(() => { if (isEditMode) return; if (step2Done) { resetTestState(); } else if (step1Done) { fullReset(); } }, [step2Done, step1Done, fullReset, isEditMode, resetTestState]);
    useImperativeHandle(ref, () => ({ stepBack, reset: fullReset }), [stepBack, fullReset]);
    useEffect(() => { onStateChange?.({ selectedProvider: provider, testStatus, testMessage, createdProviderId: createdProviderIdRef.current, step1Done, step2Done, canStepBack, isEditMode, useEnvVar }); }, [provider, testStatus, testMessage, step1Done, step2Done, canStepBack, isEditMode, useEnvVar, onStateChange, createdProviderIdRef]);
    const runTestRef = useRef(runTest); runTestRef.current = runTest;
    const testStatusRef = useRef(testStatus); testStatusRef.current = testStatus;
    const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
    useEffect(() => {
      if (!autoTest || !step1Done || isEditMode) return;
      if (testStatusRef.current === "success" || testStatusRef.current === "testing") return;
      if (!isOllama && apiKey.trim().length === 0) return;
      clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => { if (testStatusRef.current !== "success" && testStatusRef.current !== "testing") runTestRef.current(); }, autoTestDelay);
      return () => clearTimeout(debounceRef.current);
    }, [apiKey, baseUrl, step1Done, isOllama, autoTest, autoTestDelay, isEditMode]);
    const clearInput = () => { if (testStatus !== "idle") resetTestState(); };
    const badge = (n: string | ReactNode, done: boolean, active: boolean) => (
      <div className={`w-7 h-7 flex items-center justify-center rounded-full text-xs font-semibold shrink-0 ${done ? "bg-[var(--success-9)] text-on-accent" : active ? "bg-[var(--interactive-default)] text-on-accent" : "bg-[var(--surface-primary)] border border-[var(--border-default)] text-[var(--text-muted)]"}`}>{done ? <Check className="size-4" strokeWidth={2} /> : n}</div>
    );
    return (
      <div>
        <div className="mb-1">
          <div className="flex items-center gap-3 mb-4">{badge("1", step1Done, true)}<span className={`text-[16px] font-medium ${step1Done ? "text-[var(--text-muted)] line-through opacity-70" : "text-[var(--text-primary)]"}`}>Step 1: Select Provider</span></div>
          {step1Done && provider && <div className="flex items-center gap-2 px-3 py-2 bg-success-3 border border-[var(--success-9)] rounded-md text-[var(--success-9)] text-[13px] font-medium mb-4"><Check className="size-4" strokeWidth={2} /><span>{provider.name} selected</span></div>}
          {!isEditMode && (<div className={`flex flex-col gap-3 ${step1Done ? "opacity-60" : ""}`}>
            {HERO_PROVIDERS.map((p) => (<button key={p.id} type="button" onClick={() => selectProvider(p.id)} disabled={step1Done && selectedProviderId !== p.id} className={`flex items-center gap-4 px-4 py-3 rounded-md transition-all text-left ${selectedProviderId === p.id ? "border border-[var(--success-9)] bg-success-3" : "bg-[var(--surface-primary)] border border-[var(--border-default)]"} ${step1Done && selectedProviderId !== p.id ? "hidden" : ""}`}><div className="w-10 h-10 flex items-center justify-center bg-[var(--surface-raised)] rounded-md text-xl shrink-0">{p.emoji}</div><div className="flex-1 min-w-0"><div className="text-[14px] font-medium text-[var(--text-primary)] mb-0.5">{p.name}</div><div className="text-[12px] text-[var(--text-muted)]">{p.desc}</div></div>{selectedProviderId === p.id && <Check className="size-5 text-[var(--success-9)] shrink-0" strokeWidth={2} />}</button>))}
            {step1Done && provider && DROPDOWN_PROVIDERS.some((p) => p.id === selectedProviderId) && (<div className="flex items-center gap-4 px-4 py-3 rounded-md border border-[var(--success-9)] bg-success-3"><div className="w-10 h-10 flex items-center justify-center bg-[var(--surface-raised)] rounded-md text-xl shrink-0">{provider.emoji}</div><div className="flex-1 min-w-0"><div className="text-[14px] font-medium text-[var(--text-primary)] mb-0.5">{provider.name}</div><div className="text-[12px] text-[var(--text-muted)]">{provider.desc}</div></div><Check className="size-5 text-[var(--success-9)] shrink-0" strokeWidth={2} /></div>)}
            {!step1Done && (<div><Label className="block text-[11px] font-semibold tracking-[0.08em] uppercase text-[var(--text-muted)] mb-2 mt-2">Other Provider</Label><Select value={dropdownValue} onValueChange={(v) => { if (v) selectProvider(v); }}><SelectTrigger className="h-9 w-full bg-[var(--surface-primary)] border-[var(--border-default)]"><SelectValue placeholder="Select a provider…" /></SelectTrigger><SelectContent>{DROPDOWN_PROVIDERS.map((p) => (<SelectItem key={p.id} value={p.id}><span className="inline-flex items-center gap-2"><span>{p.emoji}</span><span>{p.name}</span><span className="text-[var(--text-muted)]">— {p.desc}</span></span></SelectItem>))}</SelectContent></Select></div>)}
          </div>)}
        </div>
        <div className="h-px bg-[var(--border-default)] my-6" />
        <div className="mb-1">
          <div className="flex items-center gap-3 mb-4">{badge("2", step2Done, step1Done)}<span className={`text-[16px] font-medium ${step2Done ? "text-[var(--text-muted)] line-through opacity-70" : step1Done ? "text-[var(--text-primary)]" : "text-[var(--text-muted)]"}`}>Step 2: Configure</span></div>
          {step1Done && provider && (<>
            {!step2Done && (<div className="mb-4"><Label className="block text-[11px] font-semibold tracking-[0.08em] uppercase text-[var(--text-muted)] mb-2">Display Name</Label><Input type="text" value={displayName} onChange={(e) => { setDisplayName(e.target.value); clearInput(); }} placeholder={provider.name} className="h-9 px-3 bg-[var(--surface-secondary)] border-[var(--border-default)] text-sm" /></div>)}
            {!step2Done && !isOllama && (<div className="mb-4"><div className="flex items-center justify-between mb-2"><Label className="block text-[11px] font-semibold tracking-[0.08em] uppercase text-[var(--text-muted)]">{useEnvVar ? "Environment Variable Name" : "API Key"}</Label><div className="flex items-center gap-2"><span className="text-[11px] text-[var(--text-muted)]">Use environment variable</span><Switch checked={useEnvVar} onCheckedChange={setUseEnvVar} aria-label="Use environment variable" /></div></div>{useEnvVar ? (<Input type="text" placeholder={provider?.apiKeyEnv || "OPENAI_API_KEY"} value={envVarName} onChange={(e) => { setEnvVarName(e.target.value); clearInput(); }} className="h-9 px-3 bg-[var(--surface-secondary)] border-[var(--border-default)] font-mono text-sm" autoFocus />) : (<div className="relative"><Input type={showApiKey ? "text" : "password"} placeholder={isEditMode && editing?.hasKey ? "••••••••••••(leave empty to keep)" : "sk-••••••••••••••••••••••••••••••"} value={apiKey} onChange={(e) => { setApiKey(e.target.value); clearInput(); }} className="h-9 px-3 pr-9 bg-[var(--surface-secondary)] border-[var(--border-default)] font-mono text-sm" autoFocus={!isEditMode} /><button type="button" onClick={() => setShowApiKey(!showApiKey)} className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)]">{showApiKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button></div>)}</div>)}
            {!step2Done && (<div className="mb-4"><Label className="block text-[11px] font-semibold tracking-[0.08em] uppercase text-[var(--text-muted)] mb-2">Base URL <span className="normal-case font-normal">(optional)</span></Label><Input type="url" value={baseUrl} onChange={(e) => { setBaseUrl(e.target.value); clearInput(); }} placeholder={isOllama ? "http://localhost:11434" : "https://api.provider.com/v1"} className="h-9 px-3 bg-[var(--surface-secondary)] border-[var(--border-default)] font-mono text-sm" />{!isOllama && <p className="text-[11px] text-[var(--text-muted)] mt-1">Override default endpoint for proxies or enterprise deployments</p>}</div>)}
            <div className="flex items-center gap-3">
              {testStatus === "testing" && <div className="flex items-center gap-2 text-[13px] text-[var(--text-muted)]"><Loader2 className="size-4 animate-spin" strokeWidth={2} /><span>Testing connection…</span></div>}
              {testStatus === "success" && <div className="flex items-center gap-2 px-3 py-2 bg-success-3 border border-[var(--success-9)] rounded-md text-[var(--success-9)] text-[13px]"><Check className="size-4" strokeWidth={2} /><span>{testMessage}</span></div>}
              {testStatus === "error" && <div className="flex items-center gap-2 text-[13px] text-[var(--danger-9)]"><XCircle className="size-4" strokeWidth={2} /><span>{testMessage}</span></div>}
            </div>
          </>)}
          {!step1Done && <div className="p-4 bg-[var(--surface-primary)] border border-dashed border-[var(--border-default)] rounded-md text-[var(--text-muted)] text-[13px] text-center">Select a provider first</div>}
        </div>
        <div className="h-px bg-[var(--border-default)] my-6" />
        <div className={`mb-1 ${!step2Done ? "opacity-50" : ""}`}>
          <div className="flex items-center gap-3 mb-4">{badge("3", false, step2Done)}<span className={`text-[16px] font-medium ${step2Done ? "text-[var(--text-primary)]" : "text-[var(--text-muted)]"}`}>Step 3: Confirm Setup</span></div>
          {step2Done && provider ? (<><div className="p-4 bg-[var(--surface-primary)] border border-[var(--border-default)] rounded-md mb-4"><div className="flex items-center justify-between mb-2"><span className="text-[14px] font-medium text-[var(--text-primary)]">{displayName || provider.name}</span><span className="flex items-center gap-2 text-[var(--success-9)] text-[13px]"><Check className="size-4" strokeWidth={2} />Connected</span></div><div className="flex justify-between text-[13px]"><span className="text-[var(--text-muted)]">Model families</span><span className="text-[var(--text-primary)] font-mono">{provider.families}</span></div></div>{confirmAction}</>) : (<div className="p-4 bg-[var(--surface-primary)] border border-dashed border-[var(--border-default)] rounded-md text-[var(--text-muted)] text-[13px] text-center">Complete previous steps to finish setup</div>)}
        </div>
      </div>
    );
  },
);
