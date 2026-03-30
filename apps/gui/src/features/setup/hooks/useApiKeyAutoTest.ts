import { useState, useRef, useCallback, useEffect } from "react";
import type { TestStatus } from "@/components/provider";
import {
  useCreateProvider,
  useDeleteProvider,
  useTestProviderConnection,
  useUpdateProvider,
} from "@/queries/settings";

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
  providerId: string | null;
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
  const [providerId, setProviderId] = useState<string | null>(editing?.id ?? null);

  const createProvider = useCreateProvider();
  const testConnection = useTestProviderConnection();
  const deleteProvider = useDeleteProvider();
  const updateProvider = useUpdateProvider();

  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const providerIdRef = useRef<string | null>(editing?.id ?? null);

  const reset = useCallback(() => {
    clearTimeout(debounceRef.current);
    setTestStatus("idle");
    setTestMessage("");
    setModels([]);
    setProviderId(editing?.id ?? null);
    providerIdRef.current = editing?.id ?? null;
  }, [editing?.id]);

  const cleanup = useCallback(() => {
    clearTimeout(debounceRef.current);
    const pid = providerIdRef.current;
    if (pid && !editing) {
      deleteProvider.mutate(pid);
    }
    reset();
  }, [deleteProvider, editing, reset]);

  const runAutoTest = useCallback(async () => {
    const trimmedKey = apiKey.trim();
    const isOllama = providerType === "ollama";
    if (!trimmedKey && !isOllama && !editing) return;

    setTestStatus("testing");
    setTestMessage("");
    setModels([]);

    try {
      let pid = providerIdRef.current;

      if (editing) {
        pid = editing.id;
        providerIdRef.current = pid;
        setProviderId(pid);

        await updateProvider.mutateAsync({
          id: pid,
          data: {
            api_key_env: trimmedKey || undefined,
            base_url: baseUrl.trim() || undefined,
          },
        });
      } else if (!pid) {
        const created = await createProvider.mutateAsync({
          name: providerName || providerType,
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
  }, [providerType, providerName, apiKey, baseUrl, editing, createProvider, testConnection, updateProvider]);

  const runAutoTestRef = useRef(runAutoTest);
  runAutoTestRef.current = runAutoTest;

  useEffect(() => {
    const trimmedKey = apiKey.trim();
    const isOllama = providerType === "ollama";
    if (!trimmedKey && !isOllama && !editing) return;

    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      runAutoTestRef.current();
    }, 1000);

    return () => clearTimeout(debounceRef.current);
  }, [apiKey, baseUrl, providerType, editing]);

  return { testStatus, testMessage, models, providerId, reset, cleanup };
}
