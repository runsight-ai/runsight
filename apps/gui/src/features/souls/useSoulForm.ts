import { useCallback, useRef, useState } from "react";

import { useCreateSoul, useUpdateSoul } from "@/queries/souls";
import type { SoulResponse } from "@runsight/shared/zod";

interface SoulFormValues {
  name: string;
  avatarColor: string;
  providerId: string | null;
  provider: string | null;
  modelId: string | null;
  systemPrompt: string;
  tools: string[];
  temperature: number;
  maxTokens: number | null;
  maxToolIterations: number;
}

interface UseSoulFormOptions {
  mode: "create" | "edit";
  soulId?: string;
  initial?: SoulResponse | null;
  onSuccess?: (soul: SoulResponse) => void;
}

interface UseSoulFormResult {
  values: SoulFormValues;
  isDirty: boolean;
  isSubmitting: boolean;
  setField: <K extends keyof SoulFormValues>(field: K, value: SoulFormValues[K]) => void;
  submit: () => Promise<SoulResponse>;
  reset: (soul?: SoulResponse | null) => void;
}

const DEFAULT_VALUES: SoulFormValues = {
  name: "",
  avatarColor: "accent",
  providerId: null,
  provider: null,
  modelId: null,
  systemPrompt: "",
  tools: [],
  temperature: 0.7,
  maxTokens: null,
  maxToolIterations: 5,
};

function toFormValues(soul?: SoulResponse | null): SoulFormValues {
  if (!soul) {
    return DEFAULT_VALUES;
  }

  return {
    name: soul.role ?? "",
    avatarColor: soul.avatar_color ?? "accent",
    providerId: soul.provider ?? null,
    provider: soul.provider ?? null,
    modelId: soul.model_name ?? null,
    systemPrompt: soul.system_prompt ?? "",
    tools: soul.tools ?? [],
    temperature: soul.temperature ?? 0.7,
    maxTokens: soul.max_tokens ?? null,
    maxToolIterations: soul.max_tool_iterations ?? 5,
  };
}

export function useSoulForm({
  mode,
  soulId,
  initial,
  onSuccess,
}: UseSoulFormOptions): UseSoulFormResult {
  const createSoul = useCreateSoul();
  const updateSoul = useUpdateSoul();
  const initialValuesRef = useRef<SoulFormValues>(toFormValues(initial));
  const [values, setValues] = useState<SoulFormValues>(initialValuesRef.current);

  const isDirty = JSON.stringify(values) !== JSON.stringify(initialValuesRef.current);

  const setField = useCallback(<K extends keyof SoulFormValues>(field: K, value: SoulFormValues[K]) => {
    setValues((current) => {
      if (field === "providerId") {
        return {
          ...current,
          providerId: value as string | null,
          provider: value as string | null,
          modelId: null,
        };
      }

      return { ...current, [field]: value };
    });
  }, []);

  const reset = useCallback((soul?: SoulResponse | null) => {
    const nextValues = toFormValues(soul ?? initial ?? null);
    initialValuesRef.current = nextValues;
    setValues(nextValues);
  }, [initial]);

  const submit = useCallback(async () => {
    const payload = {
      role: values.name,
      system_prompt: values.systemPrompt,
      model_name: values.modelId,
      provider: values.provider,
      tools: values.tools.length > 0 ? values.tools : null,
      temperature: values.temperature !== 0.7 ? values.temperature : null,
      max_tokens: values.maxTokens,
      max_tool_iterations:
        values.maxToolIterations !== 5 ? values.maxToolIterations : null,
      avatar_color: values.avatarColor,
    };

    const result =
      mode === "edit" && soulId
        ? await updateSoul.mutateAsync({
            id: soulId,
            data: {
              ...payload,
              copy_on_edit: false,
            },
          })
        : await createSoul.mutateAsync(payload);

    initialValuesRef.current = toFormValues(result);
    setValues(initialValuesRef.current);
    onSuccess?.(result);
    return result;
  }, [createSoul, mode, onSuccess, soulId, updateSoul, values]);

  return {
    values,
    isDirty,
    isSubmitting: createSoul.isPending || updateSoul.isPending,
    setField,
    submit,
    reset,
  };
}

export type { SoulFormValues, UseSoulFormOptions, UseSoulFormResult };
