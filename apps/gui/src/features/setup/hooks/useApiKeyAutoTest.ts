import { useState, useRef, useCallback, useEffect } from "react";
import type { TestStatus } from "@/components/provider";
import { useTestProviderCredentials } from "@/queries/settings";

interface UseApiKeyAutoTestParams {
  providerType: string;
  providerName?: string;
  apiKey: string;
  baseUrl: string;
  editing?: {
    id: string;
  };
}

interface UseApiKeyAutoTestReturn {
  testStatus: TestStatus;
  testMessage: string;
  models: string[];
  reset: () => void;
  cleanup: () => void;
}

export function useApiKeyAutoTest({
  providerType,
  providerName,
  apiKey,
  baseUrl,
  editing,
}: UseApiKeyAutoTestParams): UseApiKeyAutoTestReturn {
  const [testStatus, setTestStatus] = useState<TestStatus>("idle");
  const [testMessage, setTestMessage] = useState("");
  const [models, setModels] = useState<string[]>([]);

  const testCredentials = useTestProviderCredentials();

  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const reset = useCallback(() => {
    clearTimeout(debounceRef.current);
    setTestStatus("idle");
    setTestMessage("");
    setModels([]);
  }, []);

  const cleanup = useCallback(() => {
    clearTimeout(debounceRef.current);
    reset();
  }, [reset]);

  const runAutoTest = useCallback(async () => {
    const trimmedKey = apiKey.trim();
    const trimmedBaseUrl = baseUrl.trim();
    const isOllama = providerType === "ollama";
    if (!trimmedKey && !isOllama && !editing?.id) return;

    setTestStatus("testing");
    setTestMessage("");
    setModels([]);

    try {
      const result = await testCredentials.mutateAsync({
        provider_id: editing?.id,
        provider_type: providerType,
        name: providerName || providerType,
        api_key_env: trimmedKey || undefined,
        base_url: trimmedBaseUrl || undefined,
      });

      if (result.success) {
        setTestStatus("success");
        setTestMessage(result.message ?? "Connection successful");
        setModels(result.models ?? []);
      } else {
        setTestStatus("error");
        setTestMessage(result.message ?? "Connection failed");
      }
    } catch (err) {
      setTestStatus("error");
      setTestMessage(err instanceof Error ? err.message : "Connection failed");
    }
  }, [providerType, providerName, apiKey, baseUrl, editing?.id, testCredentials]);

  const runAutoTestRef = useRef(runAutoTest);
  runAutoTestRef.current = runAutoTest;

  useEffect(() => {
    const trimmedKey = apiKey.trim();
    const isOllama = providerType === "ollama";
    if (!trimmedKey && !isOllama && !editing?.id) return;

    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      runAutoTestRef.current();
    }, 1000);

    return () => clearTimeout(debounceRef.current);
  }, [apiKey, baseUrl, providerType, editing?.id]);

  return { testStatus, testMessage, models, reset, cleanup };
}
