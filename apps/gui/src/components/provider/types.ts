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
