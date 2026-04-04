import { useCallback, useEffect, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Button } from "@runsight/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@runsight/ui/dialog";
import { Input } from "@runsight/ui/input";
import { Label } from "@runsight/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@runsight/ui/select";
import { ALL_PROVIDERS } from "./ProviderSetup";
import type { EditingProvider, ProviderDef } from "./ProviderSetup";
import { ConnectionFeedback } from "@/features/setup/components/ConnectionFeedback";
import { useApiKeyAutoTest } from "@/features/setup/hooks/useApiKeyAutoTest";
import {
  useCreateProvider,
  useTestProviderConnection,
  useUpdateProvider,
} from "@/queries/settings";

export interface ProviderModalProps {
  mode: "settings-add" | "settings-edit" | "canvas";
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editing?: EditingProvider;
  onSaveSuccess?: (providerId: string) => void;
}

export type ProviderModalMode = ProviderModalProps["mode"];

const PROVIDER_DOCS_URLS: Record<string, string> = {
  openai: "https://platform.openai.com/api-keys",
  anthropic: "https://console.anthropic.com/settings/keys",
  google: "https://aistudio.google.com/app/apikey",
  azure_openai: "https://portal.azure.com/#view/Microsoft_Azure_ProjectOxford/CognitiveServicesHub",
  aws_bedrock: "https://docs.aws.amazon.com/bedrock/latest/userguide/setting-up.html",
  mistral: "https://console.mistral.ai/api-keys",
  cohere: "https://dashboard.cohere.com/api-keys",
  groq: "https://console.groq.com/keys",
  together: "https://api.together.xyz/settings/api-keys",
  ollama: "https://ollama.com/download",
  custom: "https://platform.openai.com/docs/api-reference",
};

const API_KEY_PLACEHOLDERS: Record<string, string> = {
  openai: "sk-proj-...",
  anthropic: "sk-ant-...",
  google: "AIza...",
  azure_openai: "Paste your Azure API key",
  aws_bedrock: "Paste your AWS Bedrock API key",
  mistral: "Paste your Mistral API key",
  cohere: "Paste your Cohere API key",
  groq: "gsk_...",
  together: "Paste your Together API key",
  ollama: "No API key required",
  custom: "Paste your provider API key",
};

function getDocsUrl(provider: ProviderDef): string {
  return PROVIDER_DOCS_URLS[provider.id] ?? "";
}

export function ProviderModal({
  mode,
  open,
  onOpenChange,
  editing,
  onSaveSuccess,
}: ProviderModalProps) {
  const createProvider = useCreateProvider();
  const updateProvider = useUpdateProvider();
  const testConnection = useTestProviderConnection();
  const initialProviderId = editing?.type ?? "openai";
  const [selectedProviderId, setSelectedProviderId] = useState(initialProviderId);
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [baseUrl, setBaseUrl] = useState(editing?.baseUrl ?? "");

  useEffect(() => {
    if (!open) {
      return;
    }

    setSelectedProviderId(editing?.type ?? "openai");
    setApiKey("");
    setShowApiKey(false);
    setBaseUrl(editing?.baseUrl ?? "");
  }, [editing?.baseUrl, editing?.type, open]);

  const provider: ProviderDef =
    ALL_PROVIDERS.find((item) => item.id === selectedProviderId) ?? ALL_PROVIDERS[0]!;
  const isCustomProvider = provider.isCustom === true;
  const isOllama = provider.id === "ollama";
  const showBaseUrl = isCustomProvider || isOllama;
  const isEditMode = mode === "settings-edit";

  const { cleanup, models, reset, testMessage, testStatus } =
    useApiKeyAutoTest({
      providerType: selectedProviderId,
      providerName: provider.name,
      apiKey,
      baseUrl,
      editing: editing ? { id: editing.id } : undefined,
    });

  const helperUrl = getDocsUrl(provider);
  const apiKeyPlaceholder = isEditMode
    ? "Leave empty to keep existing key"
    : API_KEY_PLACEHOLDERS[provider.id] ?? "Paste your API key";
  const title =
    mode === "canvas"
      ? "Add API Key"
      : isEditMode && editing
        ? `Edit ${editing.name}`
        : "Add Provider";
  const saveLabel = mode === "canvas" ? "Save & Run" : "Save";
  const isSaving =
    createProvider.isPending ||
    updateProvider.isPending ||
    testConnection.isPending;

  const handleProviderChange = useCallback(
    (value: string | null) => {
      if (!value || isEditMode) return;
      cleanup();
      setSelectedProviderId(value);
      setApiKey("");
      setShowApiKey(false);
      setBaseUrl(value === "ollama" ? "http://localhost:11434" : "");
      reset();
    },
    [cleanup, isEditMode, reset],
  );

  const handleClose = useCallback(() => {
    cleanup();
    setApiKey("");
    setShowApiKey(false);
    setBaseUrl(editing?.baseUrl ?? "");
    setSelectedProviderId(editing?.type ?? "openai");
    onOpenChange(false);
  }, [cleanup, editing?.baseUrl, editing?.type, onOpenChange]);

  async function handleSave() {
    if (testStatus !== "success") return;

    const payload = {
      api_key_env: apiKey.trim() || undefined,
      base_url: showBaseUrl ? baseUrl.trim() || undefined : undefined,
    };

    try {
      let savedProviderId = editing?.id ?? "";

      if (isEditMode && editing) {
        const updated = await updateProvider.mutateAsync({
          id: editing.id,
          data: payload,
        });
        savedProviderId = updated.id;
      } else {
        const created = await createProvider.mutateAsync({
          name: provider.name,
          api_key_env: payload.api_key_env,
          base_url: payload.base_url,
        });
        savedProviderId = created.id;
      }

      await testConnection.mutateAsync(savedProviderId);
      onSaveSuccess?.(savedProviderId);
      reset();
      onOpenChange(false);
    } catch {
      // Query hooks surface user-facing toasts.
    }
  }

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen ? handleClose() : onOpenChange(nextOpen)}>
      <DialogContent className="max-w-[440px]">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <DialogBody className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <Label>Provider</Label>
            <Select
              value={selectedProviderId}
              onValueChange={handleProviderChange}
              disabled={isEditMode}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a provider..." />
              </SelectTrigger>
              <SelectContent>
                {ALL_PROVIDERS.map((item) => (
                  <SelectItem key={item.id} value={item.id}>
                    <span className="inline-flex items-center gap-2">
                      <span>{item.emoji}</span>
                      <span>{item.name}</span>
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-2">
            <Label>API Key</Label>
            <div className="relative">
              <Input
                type={showApiKey ? "text" : "password"}
                placeholder={apiKeyPlaceholder}
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                className="pr-8 font-mono"
                autoComplete="off"
                spellCheck={false}
              />
              <button
                type="button"
                onClick={() => setShowApiKey((current) => !current)}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-sm border-none bg-transparent p-1 text-muted hover:text-primary"
                aria-label="Toggle key visibility"
              >
                {showApiKey ? (
                  <EyeOff className="size-3.5" />
                ) : (
                  <Eye className="size-3.5" />
                )}
              </button>
            </div>
            {helperUrl && (
              <span className="text-xs text-muted">
                Find your API key at{" "}
                <a
                  href={helperUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-secondary underline underline-offset-2 hover:text-primary"
                >
                  {helperUrl.replace("https://", "")}
                </a>
              </span>
            )}
            <ConnectionFeedback
              status={testStatus}
              message={testMessage}
              modelCount={models.length}
            />
          </div>

          {showBaseUrl && (
            <div className="flex flex-col gap-2">
              <Label>Base URL</Label>
              <Input
                type="url"
                value={baseUrl}
                onChange={(event) => setBaseUrl(event.target.value)}
                placeholder={
                  isOllama ? "http://localhost:11434" : "https://api.provider.com/v1"
                }
                className="font-mono"
              />
            </div>
          )}
        </DialogBody>

        <DialogFooter>
          <Button variant="secondary" size="sm" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            size="sm"
            disabled={testStatus !== "success"}
            loading={isSaving}
            onClick={handleSave}
          >
            {saveLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
