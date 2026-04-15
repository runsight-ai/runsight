import { useState, useCallback } from "react";
import { ALL_PROVIDERS, DROPDOWN_PROVIDERS } from "../constants";
import type { ProviderDef, EditingProvider } from "../types";

export interface ProviderFormState {
  selectedProviderId: string | null;
  dropdownValue: string;
  displayName: string;
  apiKey: string;
  showApiKey: boolean;
  useEnvVar: boolean;
  envVarName: string;
  baseUrl: string;
  provider: ProviderDef | null;
  isOllama: boolean;
  step1Done: boolean;
  setDisplayName: (v: string) => void;
  setApiKey: (v: string) => void;
  setShowApiKey: (v: boolean) => void;
  setUseEnvVar: (v: boolean) => void;
  setEnvVarName: (v: string) => void;
  setBaseUrl: (v: string) => void;
  selectProvider: (id: string) => void;
  fullReset: () => void;
}

export function useProviderSetupForm(editing?: EditingProvider): ProviderFormState {
  const initialProviderId = editing
    ? (ALL_PROVIDERS.find((p) => p.id === editing.type)?.id ?? editing.type)
    : null;

  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(initialProviderId);
  const [dropdownValue, setDropdownValue] = useState(() =>
    initialProviderId && DROPDOWN_PROVIDERS.some((p) => p.id === initialProviderId)
      ? initialProviderId
      : "",
  );
  const [displayName, setDisplayName] = useState(editing?.name ?? "");
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [useEnvVar, setUseEnvVar] = useState(false);
  const [envVarName, setEnvVarName] = useState("");
  const [baseUrl, setBaseUrl] = useState(editing?.baseUrl ?? "");

  const provider = ALL_PROVIDERS.find((p) => p.id === selectedProviderId) ?? null;
  const isOllama = selectedProviderId === "ollama";
  const step1Done = selectedProviderId != null;

  const fullReset = useCallback(() => {
    setSelectedProviderId(null);
    setDropdownValue("");
    setDisplayName("");
    setApiKey("");
    setBaseUrl("");
    setShowApiKey(false);
    setUseEnvVar(false);
    setEnvVarName("");
  }, []);

  const selectProvider = useCallback((id: string) => {
    setSelectedProviderId(id);
    setDropdownValue(DROPDOWN_PROVIDERS.some((p) => p.id === id) ? id : "");
    const catalogName = ALL_PROVIDERS.find((p) => p.id === id)?.name ?? "";
    setDisplayName(catalogName);
    setApiKey("");
    setUseEnvVar(false);
    setEnvVarName("");
    setBaseUrl(id === "ollama" ? "http://localhost:11434" : "");
  }, []);

  return {
    selectedProviderId, dropdownValue, displayName, apiKey, showApiKey,
    useEnvVar, envVarName, baseUrl, provider, isOllama, step1Done,
    setDisplayName, setApiKey, setShowApiKey, setUseEnvVar, setEnvVarName,
    setBaseUrl, selectProvider, fullReset,
  };
}
