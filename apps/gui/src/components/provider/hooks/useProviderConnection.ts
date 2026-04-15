import { useState, useRef, useCallback } from "react";
import type { MutableRefObject } from "react";
import { useCreateProvider, useUpdateProvider, useTestProviderConnection } from "@/queries/settings";
import type { ProviderDef, TestStatus, EditingProvider } from "../types";

interface UseProviderConnectionOptions {
  provider: ProviderDef | null;
  apiKey: string;
  baseUrl: string;
  displayName: string;
  isOllama: boolean;
  isEditMode: boolean;
  editing?: EditingProvider;
  useEnvVar: boolean;
  envVarName: string;
}

export interface ConnectionState {
  testStatus: TestStatus;
  testMessage: string;
  createdProviderIdRef: MutableRefObject<string | null>;
  runTest: () => Promise<void>;
  resetTestState: () => void;
}

export function useProviderConnection(opts: UseProviderConnectionOptions): ConnectionState {
  const {
    provider, apiKey, baseUrl, displayName,
    isOllama, isEditMode, editing, useEnvVar, envVarName,
  } = opts;

  const createProvider = useCreateProvider();
  const updateProvider = useUpdateProvider();
  const testConnection = useTestProviderConnection();

  const [testStatus, setTestStatus] = useState<TestStatus>("idle");
  const [testMessage, setTestMessage] = useState("");
  const createdProviderIdRef = useRef<string | null>(null);

  const resetTestState = useCallback(() => {
    setTestStatus("idle");
    setTestMessage("");
    createdProviderIdRef.current = null;
  }, []);

  const runTest = useCallback(async () => {
    if (!provider) return;
    const currentKey = apiKey.trim();
    const currentBaseUrl = baseUrl.trim();
    const envVarValue = useEnvVar ? envVarName.trim() : "";
    if (!currentKey && !envVarValue && !isOllama && !isEditMode) return;
    setTestStatus("testing");
    setTestMessage("");
    try {
      let pid: string;
      if (isEditMode && editing) {
        const patchFields: Record<string, string | undefined> = {};
        if (displayName && displayName !== editing.name) patchFields.name = displayName;
        if (useEnvVar && envVarName.trim()) { patchFields.api_key_env = envVarName.trim(); }
        else if (currentKey) { patchFields.api_key_env = currentKey; }
        if (currentBaseUrl !== (editing.baseUrl ?? "")) patchFields.base_url = currentBaseUrl || undefined;
        if (Object.keys(patchFields).length > 0) { await updateProvider.mutateAsync({ id: editing.id, data: { id: editing.id, kind: "provider", ...patchFields } }); }
        pid = editing.id;
      } else {
        pid = createdProviderIdRef.current!;
        if (!pid) {
          const created = await createProvider.mutateAsync({
            id: provider.id,
            kind: "provider",
            name: displayName || provider.name,
            api_key_env: useEnvVar ? envVarName.trim() : (currentKey || undefined),
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

  return { testStatus, testMessage, createdProviderIdRef, runTest, resetTestState };
}
