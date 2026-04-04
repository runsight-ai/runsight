import { useState, useEffect, useRef, useCallback, useImperativeHandle, forwardRef } from "react";
import type { ReactNode } from "react";
import { Input } from "@runsight/ui/input";
import { Label } from "@runsight/ui/label";
import { Switch } from "@runsight/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@runsight/ui/select";
import { useCreateProvider, useUpdateProvider, useTestProviderConnection } from "@/queries/settings";
import { Check, Loader2, XCircle, Eye, EyeOff } from "lucide-react";

export interface ProviderDef {
  id: string;
  name: string;
  desc: string;
  families: string;
  emoji: string;
  apiKeyEnv: string;
  isBaseUrlOnly?: boolean;
  isCustom?: boolean;
}

export const HERO_PROVIDERS: ProviderDef[] = [
  { id: "openai", name: "OpenAI", desc: "GPT, GPT Codex, o-series", families: "GPT, GPT Codex", emoji: "🤖", apiKeyEnv: "OPENAI_API_KEY" },
  { id: "anthropic", name: "Anthropic", desc: "Haiku, Sonnet, Opus", families: "Haiku, Sonnet, Opus", emoji: "🧠", apiKeyEnv: "ANTHROPIC_API_KEY" },
];

export const DROPDOWN_PROVIDERS: ProviderDef[] = [
  { id: "google", name: "Google", desc: "Gemini Pro, Gemini Flash", families: "Gemini", emoji: "🔷", apiKeyEnv: "GOOGLE_API_KEY" },
  { id: "azure_openai", name: "Azure OpenAI", desc: "OpenAI models via Azure", families: "GPT (Azure)", emoji: "☁️", apiKeyEnv: "AZURE_OPENAI_API_KEY" },
  { id: "aws_bedrock", name: "AWS Bedrock", desc: "Claude, Titan via AWS", families: "Multi-provider", emoji: "🟠", apiKeyEnv: "AWS_ACCESS_KEY_ID" },
  { id: "mistral", name: "Mistral", desc: "Mistral Large, Codestral", families: "Mistral", emoji: "🌪️", apiKeyEnv: "MISTRAL_API_KEY" },
  { id: "cohere", name: "Cohere", desc: "Command R+, Embed", families: "Command", emoji: "💬", apiKeyEnv: "COHERE_API_KEY" },
  { id: "groq", name: "Groq", desc: "LLaMA, Mixtral (fast)", families: "LLaMA, Mixtral", emoji: "⚡", apiKeyEnv: "GROQ_API_KEY" },
  { id: "together", name: "Together AI", desc: "Open-source models", families: "Open-source", emoji: "🔗", apiKeyEnv: "TOGETHER_API_KEY" },
  { id: "ollama", name: "Ollama", desc: "Run models locally", families: "Local models", emoji: "🦙", apiKeyEnv: "OLLAMA_API_BASE", isBaseUrlOnly: true },
  { id: "custom", name: "Custom", desc: "Any OpenAI-compatible endpoint", families: "Custom", emoji: "⚙️", apiKeyEnv: "CUSTOM_API_KEY", isCustom: true },
];

export const ALL_PROVIDERS = [...HERO_PROVIDERS, ...DROPDOWN_PROVIDERS];

export type TestStatus = "idle" | "testing" | "success" | "error";

export interface ProviderSetupState {
  selectedProvider: ProviderDef | null;
  testStatus: TestStatus;
  testMessage: string;
  createdProviderId: string | null;
  step1Done: boolean;
  step2Done: boolean;
  canStepBack: boolean;
  isEditMode: boolean;
  useEnvVar: boolean;
}

export interface ProviderSetupRef {
  stepBack: () => void;
  reset: () => void;
}

export interface EditingProvider {
  id: string;
  name: string;
  type: string;
  baseUrl?: string | null;
  hasKey: boolean;
}

interface ProviderSetupProps {
  onStateChange?: (state: ProviderSetupState) => void;
  confirmAction?: ReactNode;
  autoTest?: boolean;
  autoTestDelay?: number;
  editing?: EditingProvider;
}

export const ProviderSetup = forwardRef<ProviderSetupRef, ProviderSetupProps>(
  function ProviderSetup({ onStateChange, confirmAction, autoTest = true, autoTestDelay = 1200, editing }, ref) {
    const createProvider = useCreateProvider();
    const updateProvider = useUpdateProvider();
    const testConnection = useTestProviderConnection();

    const isEditMode = !!editing;

    const initialProviderId = editing
      ? (ALL_PROVIDERS.find((p) => p.id === editing.type)?.id ?? editing.type)
      : null;

    const [selectedProviderId, setSelectedProviderId] = useState<string | null>(initialProviderId);
    const [dropdownValue, setDropdownValue] = useState(() =>
      initialProviderId && DROPDOWN_PROVIDERS.some((p) => p.id === initialProviderId) ? initialProviderId : "",
    );
    const [displayName, setDisplayName] = useState(editing?.name ?? "");
    const [apiKey, setApiKey] = useState("");
    const [showApiKey, setShowApiKey] = useState(false);
    const [useEnvVar, setUseEnvVar] = useState<boolean>(false);
    const [envVarName, setEnvVarName] = useState("");
    const [baseUrl, setBaseUrl] = useState(editing?.baseUrl ?? "");
    const [testStatus, setTestStatus] = useState<TestStatus>("idle");
    const [testMessage, setTestMessage] = useState("");

    const createdProviderIdRef = useRef<string | null>(null);
    const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

    const provider = ALL_PROVIDERS.find((p) => p.id === selectedProviderId) ?? null;
    const isOllama = selectedProviderId === "ollama";

    const step1Done = selectedProviderId != null;
    const step2Done = testStatus === "success";
    const canStepBack = isEditMode ? false : step1Done;

    const fullReset = useCallback(() => {
      setSelectedProviderId(null);
      setDropdownValue("");
      setDisplayName("");
      setApiKey("");
      setBaseUrl("");
      setShowApiKey(false);
      // Reset useEnvVar toggle and env var name
      setUseEnvVar(false);
      setEnvVarName("");
      setTestStatus("idle");
      setTestMessage("");
      createdProviderIdRef.current = null;
    }, []);

    const stepBack = useCallback(() => {
      if (isEditMode) return;
      if (step2Done) {
        setTestStatus("idle");
        setTestMessage("");
      } else if (step1Done) {
        fullReset();
      }
    }, [step2Done, step1Done, fullReset, isEditMode]);

    useImperativeHandle(ref, () => ({ stepBack, reset: fullReset }), [stepBack, fullReset]);

    useEffect(() => {
      onStateChange?.({
        selectedProvider: provider,
        testStatus,
        testMessage,
        createdProviderId: createdProviderIdRef.current,
        step1Done,
        step2Done,
        canStepBack,
        isEditMode,
        useEnvVar,
      });
    }, [provider, testStatus, testMessage, step1Done, step2Done, canStepBack, isEditMode, useEnvVar, onStateChange]);

    const selectProvider = (id: string) => {
      setSelectedProviderId(id);
      setDropdownValue(DROPDOWN_PROVIDERS.some((p) => p.id === id) ? id : "");
      const catalogName = ALL_PROVIDERS.find((p) => p.id === id)?.name ?? "";
      setDisplayName(catalogName);
      setApiKey("");
      // Reset useEnvVar toggle for new provider
      setUseEnvVar(false);
      setEnvVarName("");
      setBaseUrl(id === "ollama" ? "http://localhost:11434" : "");
      setTestStatus("idle");
      setTestMessage("");
      createdProviderIdRef.current = null;
    };

    const runTest = useCallback(async () => {
      if (!provider) return;
      const currentKey = apiKey.trim();
      const currentBaseUrl = baseUrl.trim();
      const envVarValue = useEnvVar ? "$" + envVarName.trim() : "";
      if (!currentKey && !envVarValue && !isOllama && !isEditMode) return;

      setTestStatus("testing");
      setTestMessage("");
      try {
        let pid: string;

        if (isEditMode && editing) {
          const data: Record<string, string | undefined> = {};
          if (displayName && displayName !== editing.name) data.name = displayName;
          if (useEnvVar && envVarName.trim()) {
            data.api_key_env = "$" + envVarName.trim();
          } else if (currentKey) {
            data.api_key_env = currentKey;
          }
          if (currentBaseUrl !== (editing.baseUrl ?? "")) data.base_url = currentBaseUrl || undefined;
          if (Object.keys(data).length > 0) {
            await updateProvider.mutateAsync({ id: editing.id, data });
          }
          pid = editing.id;
        } else {
          pid = createdProviderIdRef.current!;
          if (!pid) {
            const created = await createProvider.mutateAsync({
              name: displayName || provider.name,
              api_key_env: useEnvVar ? "$" + envVarName.trim() : (currentKey || undefined),
              base_url: currentBaseUrl || undefined,
            });
            pid = created.id;
            createdProviderIdRef.current = created.id;
          }
        }

        const result = await testConnection.mutateAsync(pid);
        setTestStatus(result.success ? "success" : "error");
        setTestMessage(result.message ?? (result.success ? "Connection successful" : "Connection failed"));
      } catch (err) {
        setTestStatus("error");
        setTestMessage(err instanceof Error ? err.message : "Connection failed");
      }
    }, [provider, apiKey, baseUrl, displayName, isOllama, isEditMode, editing, useEnvVar, envVarName, createProvider, updateProvider, testConnection]);

    const runTestRef = useRef(runTest);
    runTestRef.current = runTest;
    const testStatusRef = useRef(testStatus);
    testStatusRef.current = testStatus;

    useEffect(() => {
      if (!autoTest || !step1Done || isEditMode) return;
      const ts = testStatusRef.current;
      if (ts === "success" || ts === "testing") return;
      const hasInput = isOllama ? true : apiKey.trim().length > 0;
      if (!hasInput) return;
      clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        const current = testStatusRef.current;
        if (current === "success" || current === "testing") return;
        runTestRef.current();
      }, autoTestDelay);
      return () => clearTimeout(debounceRef.current);
    }, [apiKey, baseUrl, step1Done, isOllama, autoTest, autoTestDelay, isEditMode]);

    const clearInput = () => {
      if (testStatus !== "idle") { setTestStatus("idle"); setTestMessage(""); }
    };

    return (
      <div>
        {/* Step 1: Select Provider */}
        <div className="mb-1">
          <div className="flex items-center gap-3 mb-4">
            <div className={`w-7 h-7 flex items-center justify-center rounded-full text-xs font-semibold shrink-0 ${
              step1Done ? "bg-[var(--success-9)] text-on-accent" : "bg-[var(--interactive-default)] text-on-accent"
            }`}>
              {step1Done ? <Check className="size-4" strokeWidth={2} /> : "1"}
            </div>
            <span className={`text-[16px] font-medium ${step1Done ? "text-[var(--text-muted)] line-through opacity-70" : "text-[var(--text-primary)]"}`}>
              Step 1: Select Provider
            </span>
          </div>

          {step1Done && provider && (
            <div className="flex items-center gap-2 px-3 py-2 bg-success-3 border border-[var(--success-9)] rounded-md text-[var(--success-9)] text-[13px] font-medium mb-4">
              <Check className="size-4" strokeWidth={2} />
              <span>{provider.name} selected</span>
            </div>
          )}

          {!isEditMode && (
            <div className={`flex flex-col gap-3 ${step1Done ? "opacity-60" : ""}`}>
              {HERO_PROVIDERS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => selectProvider(p.id)}
                  disabled={step1Done && selectedProviderId !== p.id}
                  className={`flex items-center gap-4 px-4 py-3 rounded-md transition-all text-left ${
                    selectedProviderId === p.id
                      ? "border border-[var(--success-9)] bg-success-3"
                      : "bg-[var(--surface-primary)] border border-[var(--border-default)] hover:border-[var(--border-default)]"
                  } ${step1Done && selectedProviderId !== p.id ? "hidden" : ""}`}
                >
                  <div className="w-10 h-10 flex items-center justify-center bg-[var(--surface-raised)] rounded-md text-xl shrink-0">{p.emoji}</div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[14px] font-medium text-[var(--text-primary)] mb-0.5">{p.name}</div>
                    <div className="text-[12px] text-[var(--text-muted)]">{p.desc}</div>
                  </div>
                  {selectedProviderId === p.id && <Check className="size-5 text-[var(--success-9)] shrink-0" strokeWidth={2} />}
                </button>
              ))}

              {step1Done && provider && DROPDOWN_PROVIDERS.some((p) => p.id === selectedProviderId) && (
                <div className="flex items-center gap-4 px-4 py-3 rounded-md border border-[var(--success-9)] bg-success-3 text-left">
                  <div className="w-10 h-10 flex items-center justify-center bg-[var(--surface-raised)] rounded-md text-xl shrink-0">{provider.emoji}</div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[14px] font-medium text-[var(--text-primary)] mb-0.5">{provider.name}</div>
                    <div className="text-[12px] text-[var(--text-muted)]">{provider.desc}</div>
                  </div>
                  <Check className="size-5 text-[var(--success-9)] shrink-0" strokeWidth={2} />
                </div>
              )}

              {!step1Done && (
                <div>
                  <Label className="block text-[11px] font-semibold tracking-[0.08em] uppercase text-[var(--text-muted)] mb-2 mt-2">
                    Other Provider
                  </Label>
                  <Select value={dropdownValue} onValueChange={(v) => { if (v) selectProvider(v); }}>
                    <SelectTrigger className="h-9 w-full bg-[var(--surface-primary)] border-[var(--border-default)]">
                      <SelectValue placeholder="Select a provider…" />
                    </SelectTrigger>
                    <SelectContent>
                      {DROPDOWN_PROVIDERS.map((p) => (
                        <SelectItem key={p.id} value={p.id}>
                          <span className="inline-flex items-center gap-2">
                            <span>{p.emoji}</span>
                            <span>{p.name}</span>
                            <span className="text-[var(--text-muted)]">— {p.desc}</span>
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="h-px bg-[var(--border-default)] my-6" />

        {/* Step 2: Configure */}
        <div className="mb-1">
          <div className="flex items-center gap-3 mb-4">
            <div className={`w-7 h-7 flex items-center justify-center rounded-full text-xs font-semibold shrink-0 ${
              step2Done ? "bg-[var(--success-9)] text-on-accent" : step1Done ? "bg-[var(--interactive-default)] text-on-accent" : "bg-[var(--surface-primary)] border border-[var(--border-default)] text-[var(--text-muted)]"
            }`}>
              {step2Done ? <Check className="size-4" strokeWidth={2} /> : "2"}
            </div>
            <span className={`text-[16px] font-medium ${
              step2Done ? "text-[var(--text-muted)] line-through opacity-70" : step1Done ? "text-[var(--text-primary)]" : "text-[var(--text-muted)]"
            }`}>
              Step 2: Configure
            </span>
          </div>

          {step1Done && provider && (
            <>
              {/* Display Name */}
              {!step2Done && (
                <div className="mb-4">
                  <Label className="block text-[11px] font-semibold tracking-[0.08em] uppercase text-[var(--text-muted)] mb-2">
                    Display Name
                  </Label>
                  <Input
                    type="text"
                    value={displayName}
                    onChange={(e) => { setDisplayName(e.target.value); clearInput(); }}
                    placeholder={provider.name}
                    className="h-9 px-3 bg-[var(--surface-secondary)] border-[var(--border-default)] text-sm"
                  />
                </div>
              )}

              {/* API Key */}
              {!step2Done && !isOllama && (
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <Label className="block text-[11px] font-semibold tracking-[0.08em] uppercase text-[var(--text-muted)]">
                      {useEnvVar ? "Environment Variable Name" : "API Key"}
                    </Label>
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-[var(--text-muted)]">Use environment variable</span>
                      <Switch
                        checked={useEnvVar}
                        onCheckedChange={setUseEnvVar}
                        aria-label="Use environment variable"
                      />
                    </div>
                  </div>
                  {useEnvVar ? (
                    <Input
                      type="text"
                      placeholder={provider?.apiKeyEnv || "OPENAI_API_KEY"}
                      value={envVarName}
                      onChange={(e) => { setEnvVarName(e.target.value); clearInput(); }}
                      className="h-9 px-3 bg-[var(--surface-secondary)] border-[var(--border-default)] font-mono text-sm"
                      autoFocus
                    />
                  ) : (
                    <div className="relative">
                      <Input
                        type={showApiKey ? "text" : "password"}
                        placeholder={isEditMode && editing?.hasKey ? "••••••••••••(leave empty to keep)" : "sk-••••••••••••••••••••••••••••••"}
                        value={apiKey}
                        onChange={(e) => { setApiKey(e.target.value); clearInput(); }}
                        className="h-9 px-3 pr-9 bg-[var(--surface-secondary)] border-[var(--border-default)] font-mono text-sm"
                        autoFocus={!isEditMode}
                      />
                      <button
                        type="button"
                        onClick={() => setShowApiKey(!showApiKey)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                      >
                        {showApiKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Base URL — always shown */}
              {!step2Done && (
                <div className="mb-4">
                  <Label className="block text-[11px] font-semibold tracking-[0.08em] uppercase text-[var(--text-muted)] mb-2">
                    Base URL <span className="normal-case font-normal">(optional)</span>
                  </Label>
                  <Input
                    type="url"
                    value={baseUrl}
                    onChange={(e) => { setBaseUrl(e.target.value); clearInput(); }}
                    placeholder={isOllama ? "http://localhost:11434" : "https://api.provider.com/v1"}
                    className="h-9 px-3 bg-[var(--surface-secondary)] border-[var(--border-default)] font-mono text-sm"
                  />
                  {!isOllama && (
                    <p className="text-[11px] text-[var(--text-muted)] mt-1">Override default endpoint for proxies or enterprise deployments</p>
                  )}
                </div>
              )}

              <div className="flex items-center gap-3">
                {testStatus === "testing" && (
                  <div className="flex items-center gap-2 text-[13px] text-[var(--text-muted)]">
                    <Loader2 className="size-4 animate-spin" strokeWidth={2} />
                    <span>Testing connection…</span>
                  </div>
                )}
                {testStatus === "success" && (
                  <div className="flex items-center gap-2 px-3 py-2 bg-success-3 border border-[var(--success-9)] rounded-md text-[var(--success-9)] text-[13px]">
                    <Check className="size-4" strokeWidth={2} />
                    <span>{testMessage}</span>
                  </div>
                )}
                {testStatus === "error" && (
                  <div className="flex items-center gap-2 text-[13px] text-[var(--danger-9)]">
                    <XCircle className="size-4" strokeWidth={2} />
                    <span>{testMessage}</span>
                  </div>
                )}
              </div>
            </>
          )}

          {!step1Done && (
            <div className="p-4 bg-[var(--surface-primary)] border border-dashed border-[var(--border-default)] rounded-md text-[var(--text-muted)] text-[13px] text-center">
              Select a provider first
            </div>
          )}
        </div>

        <div className="h-px bg-[var(--border-default)] my-6" />

        {/* Step 3: Confirm */}
        <div className={`mb-1 ${!step2Done ? "opacity-50" : ""}`}>
          <div className="flex items-center gap-3 mb-4">
            <div className={`w-7 h-7 flex items-center justify-center rounded-full text-xs font-semibold shrink-0 ${
              step2Done ? "bg-[var(--interactive-default)] text-on-accent" : "bg-[var(--surface-primary)] border border-[var(--border-default)] text-[var(--text-muted)]"
            }`}>
              3
            </div>
            <span className={`text-[16px] font-medium ${step2Done ? "text-[var(--text-primary)]" : "text-[var(--text-muted)]"}`}>
              Step 3: Confirm Setup
            </span>
          </div>

          {step2Done && provider ? (
            <>
              <div className="p-4 bg-[var(--surface-primary)] border border-[var(--border-default)] rounded-md mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[14px] font-medium text-[var(--text-primary)]">{displayName || provider.name}</span>
                  <span className="flex items-center gap-2 text-[var(--success-9)] text-[13px]">
                    <Check className="size-4" strokeWidth={2} />
                    Connected
                  </span>
                </div>
                <div className="flex justify-between text-[13px]">
                  <span className="text-[var(--text-muted)]">Model families</span>
                  <span className="text-[var(--text-primary)] font-mono">{provider.families}</span>
                </div>
              </div>
              {confirmAction}
            </>
          ) : (
            <div className="p-4 bg-[var(--surface-primary)] border border-dashed border-[var(--border-default)] rounded-md text-[var(--text-muted)] text-[13px] text-center">
              Complete previous steps to finish setup
            </div>
          )}
        </div>
      </div>
    );
  },
);
