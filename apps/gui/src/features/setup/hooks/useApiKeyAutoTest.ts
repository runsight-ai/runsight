import { useState, useRef, useCallback, useEffect } from "react";
import type { TestStatus } from "@/components/provider";
import { useCreateProvider, useTestProviderConnection, useDeleteProvider } from "@/queries/settings";

interface UseApiKeyAutoTestParams {
  providerType: string;
  apiKey: string;
  baseUrl: string;
}

interface UseApiKeyAutoTestReturn {
  testStatus: TestStatus;
  testMessage: string;
  models: string[];
  providerId: string | null;
  reset: () => void;
  cleanup: () => void;
}

export function useApiKeyAutoTest({
  providerType,
  apiKey,
  baseUrl,
}: UseApiKeyAutoTestParams): UseApiKeyAutoTestReturn {
  const [testStatus, setTestStatus] = useState<TestStatus>("idle");
  const [testMessage, setTestMessage] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [providerId, setProviderId] = useState<string | null>(null);

  const createProvider = useCreateProvider();
  const testConnection = useTestProviderConnection();
  const deleteProvider = useDeleteProvider();

  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const providerIdRef = useRef<string | null>(null);

  const reset = useCallback(() => {
    clearTimeout(debounceRef.current);
    setTestStatus("idle");
    setTestMessage("");
    setModels([]);
    setProviderId(null);
    providerIdRef.current = null;
  }, []);

  const cleanup = useCallback(() => {
    clearTimeout(debounceRef.current);
    const pid = providerIdRef.current;
    if (pid) {
      deleteProvider.mutate(pid);
    }
    reset();
  }, [deleteProvider, reset]);

  const runAutoTest = useCallback(async () => {
    const trimmedKey = apiKey.trim();
    const isOllama = providerType === "ollama";
    if (!trimmedKey && !isOllama) return;

    setTestStatus("testing");
    setTestMessage("");
    setModels([]);

    try {
      let pid = providerIdRef.current;

      if (!pid) {
        const created = await createProvider.mutateAsync({
          name: providerType,
          api_key_env: trimmedKey || undefined,
          base_url: baseUrl.trim() || undefined,
        });
        pid = created.id;
        providerIdRef.current = pid;
        setProviderId(pid);
      }

      const result = await testConnection.mutateAsync(pid);

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
  }, [providerType, apiKey, baseUrl, createProvider, testConnection]);

  const runAutoTestRef = useRef(runAutoTest);
  runAutoTestRef.current = runAutoTest;

  useEffect(() => {
    const trimmedKey = apiKey.trim();
    const isOllama = providerType === "ollama";
    if (!trimmedKey && !isOllama) return;

    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      runAutoTestRef.current();
    }, 1000);

    return () => clearTimeout(debounceRef.current);
  }, [apiKey, baseUrl, providerType]);

  return { testStatus, testMessage, models, providerId, reset, cleanup };
}
