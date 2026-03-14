import { useState, useEffect, useRef, useCallback, useImperativeHandle, forwardRef } from "react";
import type { ReactNode } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
      });
    }, [provider, testStatus, testMessage, step1Done, step2Done, canStepBack, isEditMode, onStateChange]);

    const selectProvider = (id: string) => {
      setSelectedProviderId(id);
      setDropdownValue(DROPDOWN_PROVIDERS.some((p) => p.id === id) ? id : "");
      const catalogName = ALL_PROVIDERS.find((p) => p.id === id)?.name ?? "";
      setDisplayName(catalogName);
      setApiKey("");
      setBaseUrl(id === "ollama" ? "http://localhost:11434" : "");
      setTestStatus("idle");
      setTestMessage("");
      createdProviderIdRef.current = null;
    };

    const runTest = useCallback(async () => {
      if (!provider) return;
      const currentKey = apiKey.trim();
      const currentBaseUrl = baseUrl.trim();
      if (!currentKey && !isOllama && !isEditMode) return;

      setTestStatus("testing");
      setTestMessage("");
      try {
        let pid: string;

        if (isEditMode && editing) {
          const data: Record<string, string | undefined> = {};
          if (displayName && displayName !== editing.name) data.name = displayName;
          if (currentKey) data.api_key_env = currentKey;
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
              api_key_env: currentKey || undefined,
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
    }, [provider, apiKey, baseUrl, displayName, isOllama, isEditMode, editing, createProvider, updateProvider, testConnection]);

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
              step1Done ? "bg-[var(--success)] text-white" : "bg-[var(--primary)] text-white"
            }`}>
              {step1Done ? <Check className="size-4" strokeWidth={2} /> : "1"}
            </div>
            <span className={`text-[16px] font-medium ${step1Done ? "text-[var(--muted-foreground)] line-through opacity-70" : "text-[var(--foreground)]"}`}>
              Step 1: Select Provider
            </span>
          </div>

          {step1Done && provider && (
            <div className="flex items-center gap-2 px-3 py-2 bg-[var(--success-10)] border border-[var(--success)] rounded-md text-[var(--success)] text-[13px] font-medium mb-4">
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
                      ? "border border-[var(--success)] bg-[var(--success-08)]"
                      : "bg-[var(--background)] border border-[var(--border)] hover:border-[var(--input)]"
                  } ${step1Done && selectedProviderId !== p.id ? "hidden" : ""}`}
                >
                  <div className="w-10 h-10 flex items-center justify-center bg-[var(--surface-elevated)] rounded-md text-xl shrink-0">{p.emoji}</div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[14px] font-medium text-[var(--foreground)] mb-0.5">{p.name}</div>
                    <div className="text-[12px] text-[var(--muted-foreground)]">{p.desc}</div>
                  </div>
                  {selectedProviderId === p.id && <Check className="size-5 text-[var(--success)] shrink-0" strokeWidth={2} />}
                </button>
              ))}

              {step1Done && provider && DROPDOWN_PROVIDERS.some((p) => p.id === selectedProviderId) && (
                <div className="flex items-center gap-4 px-4 py-3 rounded-md border border-[var(--success)] bg-[var(--success-08)] text-left">
                  <div className="w-10 h-10 flex items-center justify-center bg-[var(--surface-elevated)] rounded-md text-xl shrink-0">{provider.emoji}</div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[14px] font-medium text-[var(--foreground)] mb-0.5">{provider.name}</div>
                    <div className="text-[12px] text-[var(--muted-foreground)]">{provider.desc}</div>
                  </div>
                  <Check className="size-5 text-[var(--success)] shrink-0" strokeWidth={2} />
                </div>
              )}

              {!step1Done && (
                <div>
                  <Label className="block text-[11px] font-semibold tracking-[0.08em] uppercase text-[var(--muted-foreground)] mb-2 mt-2">
                    Other Provider
                  </Label>
                  <Select value={dropdownValue} onValueChange={(v) => { if (v) selectProvider(v); }}>
                    <SelectTrigger className="h-9 w-full bg-[var(--background)] border-[var(--border)]">
                      <SelectValue placeholder="Select a provider…" />
                    </SelectTrigger>
                    <SelectContent>
                      {DROPDOWN_PROVIDERS.map((p) => (
                        <SelectItem key={p.id} value={p.id}>
                          <span className="inline-flex items-center gap-2">
                            <span>{p.emoji}</span>
                            <span>{p.name}</span>
                            <span className="text-[var(--muted-foreground)]">— {p.desc}</span>
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

        <div className="h-px bg-[var(--border)] my-6" />

        {/* Step 2: Configure */}
        <div className="mb-1">
          <div className="flex items-center gap-3 mb-4">
            <div className={`w-7 h-7 flex items-center justify-center rounded-full text-xs font-semibold shrink-0 ${
              step2Done ? "bg-[var(--success)] text-white" : step1Done ? "bg-[var(--primary)] text-white" : "bg-[var(--background)] border border-[var(--border)] text-[var(--muted-subtle)]"
            }`}>
              {step2Done ? <Check className="size-4" strokeWidth={2} /> : "2"}
            </div>
            <span className={`text-[16px] font-medium ${
              step2Done ? "text-[var(--muted-foreground)] line-through opacity-70" : step1Done ? "text-[var(--foreground)]" : "text-[var(--muted-subtle)]"
            }`}>
              Step 2: Configure
            </span>
          </div>

          {step1Done && provider && (
            <>
              {/* Display Name */}
              {!step2Done && (
                <div className="mb-4">
                  <Label className="block text-[11px] font-semibold tracking-[0.08em] uppercase text-[var(--muted-foreground)] mb-2">
                    Display Name
                  </Label>
                  <Input
                    type="text"
                    value={displayName}
                    onChange={(e) => { setDisplayName(e.target.value); clearInput(); }}
                    placeholder={provider.name}
                    className="h-9 px-3 bg-[var(--card)] border-[var(--border)] text-sm"
                  />
                </div>
              )}

              {/* API Key */}
              {!step2Done && !isOllama && (
                <div className="mb-4">
                  <Label className="block text-[11px] font-semibold tracking-[0.08em] uppercase text-[var(--muted-foreground)] mb-2">
                    API Key
                  </Label>
                  <div className="relative">
                    <Input
                      type={showApiKey ? "text" : "password"}
                      placeholder={isEditMode && editing?.hasKey ? "••••••••••••(leave empty to keep)" : "sk-••••••••••••••••••••••••••••••"}
                      value={apiKey}
                      onChange={(e) => { setApiKey(e.target.value); clearInput(); }}
                      className="h-9 px-3 pr-9 bg-[var(--card)] border-[var(--border)] font-mono text-sm"
                      autoFocus={!isEditMode}
                    />
                    <button
                      type="button"
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                    >
                      {showApiKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                </div>
              )}

              {/* Base URL — always shown */}
              {!step2Done && (
                <div className="mb-4">
                  <Label className="block text-[11px] font-semibold tracking-[0.08em] uppercase text-[var(--muted-foreground)] mb-2">
                    Base URL <span className="normal-case font-normal">(optional)</span>
                  </Label>
                  <Input
                    type="url"
                    value={baseUrl}
                    onChange={(e) => { setBaseUrl(e.target.value); clearInput(); }}
                    placeholder={isOllama ? "http://localhost:11434" : "https://api.provider.com/v1"}
                    className="h-9 px-3 bg-[var(--card)] border-[var(--border)] font-mono text-sm"
                  />
                  {!isOllama && (
                    <p className="text-[11px] text-[var(--muted-subtle)] mt-1">Override default endpoint for proxies or enterprise deployments</p>
                  )}
                </div>
              )}

              <div className="flex items-center gap-3">
                {testStatus === "testing" && (
                  <div className="flex items-center gap-2 text-[13px] text-[var(--muted-foreground)]">
                    <Loader2 className="size-4 animate-spin" strokeWidth={2} />
                    <span>Testing connection…</span>
                  </div>
                )}
                {testStatus === "success" && (
                  <div className="flex items-center gap-2 px-3 py-2 bg-[var(--success-10)] border border-[var(--success)] rounded-md text-[var(--success)] text-[13px]">
                    <Check className="size-4" strokeWidth={2} />
                    <span>{testMessage}</span>
                  </div>
                )}
                {testStatus === "error" && (
                  <div className="flex items-center gap-2 text-[13px] text-[var(--error)]">
                    <XCircle className="size-4" strokeWidth={2} />
                    <span>{testMessage}</span>
                  </div>
                )}
              </div>
            </>
          )}

          {!step1Done && (
            <div className="p-4 bg-[var(--background)] border border-dashed border-[var(--border)] rounded-md text-[var(--muted-subtle)] text-[13px] text-center">
              Select a provider first
            </div>
          )}
        </div>

        <div className="h-px bg-[var(--border)] my-6" />

        {/* Step 3: Confirm */}
        <div className={`mb-1 ${!step2Done ? "opacity-50" : ""}`}>
          <div className="flex items-center gap-3 mb-4">
            <div className={`w-7 h-7 flex items-center justify-center rounded-full text-xs font-semibold shrink-0 ${
              step2Done ? "bg-[var(--primary)] text-white" : "bg-[var(--background)] border border-[var(--border)] text-[var(--muted-subtle)]"
            }`}>
              3
            </div>
            <span className={`text-[16px] font-medium ${step2Done ? "text-[var(--foreground)]" : "text-[var(--muted-subtle)]"}`}>
              Step 3: Confirm Setup
            </span>
          </div>

          {step2Done && provider ? (
            <>
              <div className="p-4 bg-[var(--background)] border border-[var(--border)] rounded-md mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[14px] font-medium text-[var(--foreground)]">{displayName || provider.name}</span>
                  <span className="flex items-center gap-2 text-[var(--success)] text-[13px]">
                    <Check className="size-4" strokeWidth={2} />
                    Connected
                  </span>
                </div>
                <div className="flex justify-between text-[13px]">
                  <span className="text-[var(--muted-foreground)]">Model families</span>
                  <span className="text-[var(--foreground)] font-mono">{provider.families}</span>
                </div>
              </div>
              {confirmAction}
            </>
          ) : (
            <div className="p-4 bg-[var(--background)] border border-dashed border-[var(--border)] rounded-md text-[var(--muted-subtle)] text-[13px] text-center">
              Complete previous steps to finish setup
            </div>
          )}
        </div>
      </div>
    );
  },
);
