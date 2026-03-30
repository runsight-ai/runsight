import { useState, useCallback } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogBody, DialogFooter } from "@runsight/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@runsight/ui/select";
import { Input } from "@runsight/ui/input";
import { Button } from "@runsight/ui/button";
import { Label } from "@runsight/ui/label";
import { Eye, EyeOff } from "lucide-react";
import { ALL_PROVIDERS } from "@/components/provider";
import type { ProviderDef } from "@/components/provider";
import { useApiKeyAutoTest } from "./hooks/useApiKeyAutoTest";
import { ConnectionFeedback } from "./components/ConnectionFeedback";

interface ApiKeyModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaveSuccess?: (providerId: string) => void;
  saveAndRun?: boolean;
}

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

function getDocsUrl(provider: ProviderDef): string {
  return PROVIDER_DOCS_URLS[provider.id] ?? "";
}

export function ApiKeyModal({
  open,
  onOpenChange,
  onSaveSuccess,
  saveAndRun,
}: ApiKeyModalProps) {
  const [selectedProviderId, setSelectedProviderId] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [baseUrl, setBaseUrl] = useState("");

  const provider: ProviderDef = ALL_PROVIDERS.find((p) => p.id === selectedProviderId) ?? ALL_PROVIDERS[0]!;
  const isCustomProvider = provider.isCustom === true;
  const isOllama = provider.id === "ollama";
  const showBaseUrl = isCustomProvider || isOllama;

  const { testStatus, testMessage, models, providerId, reset, cleanup } =
    useApiKeyAutoTest({
      providerType: selectedProviderId,
      apiKey,
      baseUrl,
    });

  const helperUrl = getDocsUrl(provider);

  const handleProviderChange = useCallback(
    (value: string | null) => {
      if (!value) return;
      setSelectedProviderId(value);
      setApiKey("");
      setShowApiKey(false);
      setBaseUrl(value === "ollama" ? "http://localhost:11434" : "");
      reset();
    },
    [reset],
  );

  const handleCancel = useCallback(() => {
    cleanup();
    setApiKey("");
    setShowApiKey(false);
    setBaseUrl("");
    setSelectedProviderId("openai");
    onOpenChange(false);
  }, [cleanup, onOpenChange]);

  const handleSave = useCallback(() => {
    if (testStatus !== "success" || !providerId) return;
    onSaveSuccess?.(providerId);
    onOpenChange(false);
  }, [testStatus, providerId, onSaveSuccess, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[440px]">
        <DialogHeader>
          <DialogTitle>Add API Key to Run</DialogTitle>
        </DialogHeader>

        <DialogBody className="flex flex-col gap-5">
          <p className="text-sm text-secondary leading-relaxed">
            Your workflow needs an AI provider to execute. Add an API key and you&apos;re ready to run.
          </p>

          {/* Provider select */}
          <div className="flex flex-col gap-2">
            <Label>Provider</Label>
            <Select value={selectedProviderId} onValueChange={handleProviderChange}>
              <SelectTrigger>
                <SelectValue placeholder="Select a provider..." />
              </SelectTrigger>
              <SelectContent>
                {ALL_PROVIDERS.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    <span className="inline-flex items-center gap-2">
                      <span>{p.emoji}</span>
                      <span>{p.name}</span>
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* API key input */}
          <div className="flex flex-col gap-2">
            <Label>API Key</Label>
            <div className="relative">
              <Input
                type={showApiKey ? "text" : "password"}
                placeholder="sk-..."
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="pr-8 font-mono"
                autoComplete="off"
                spellCheck={false}
              />
              <button
                type="button"
                onClick={() => setShowApiKey((prev) => !prev)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted hover:text-primary bg-transparent border-none cursor-pointer rounded-sm"
                aria-label="Toggle key visibility"
              >
                {showApiKey ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
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

          {/* Base URL — only for custom/ollama providers */}
          {showBaseUrl && (
            <div className="flex flex-col gap-2">
              <Label>Base URL</Label>
              <Input
                type="url"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={isOllama ? "http://localhost:11434" : "https://api.provider.com/v1"}
                className="font-mono"
              />
            </div>
          )}
        </DialogBody>

        <DialogFooter>
          <Button variant="secondary" size="sm" onClick={handleCancel}>
            Cancel
          </Button>
          <Button
            size="sm"
            disabled={testStatus !== "success"}
            onClick={handleSave}
          >
            {saveAndRun ? "Save & Run" : "Save & Run"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
