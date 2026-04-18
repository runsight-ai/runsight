export const queryKeys = {
  workflows: {
    all: ["workflows"] as const,
    detail: (id: string) => ["workflows", id] as const,
    regressions: (id: string) => ["workflows", id, "regressions"] as const,
  },
  runs: {
    all: ["runs"] as const,
    detail: (id: string) => ["runs", id] as const,
    logs: (id: string) => ["runs", id, "logs"] as const,
    contextAudit: (id: string) => ["runs", id, "contextAudit"] as const,
    regressions: (id: string) => ["runs", id, "regressions"] as const,
    children: (id: string) => ["runs", id, "children"] as const,
  },
  models: {
    providers: ["models", "providers"] as const,
    byProvider: (provider: string | null) => ["models", provider ?? "__none__"] as const,
  },
  souls: {
    all: ["souls"] as const,
    detail: (id: string) => ["souls", id] as const,
    usages: (id: string) => ["souls", id, "usages"] as const,
    tools: ["souls", "tools"] as const,
  },
  settings: {
    all: ["settings"] as const,
    providers: ["settings", "providers"] as const,
    provider: (id: string) => ["settings", "providers", id] as const,
    models: ["settings", "models"] as const,
    modelDefaults: ["settings", "modelDefaults"] as const,
    appSettings: ["settings", "appSettings"] as const,
    fallback: ["settings", "fallback"] as const,
  },
  git: {
    status: ["git", "status"] as const,
    log: ["git", "log"] as const,
    diff: ["git", "diff"] as const,
  },
  dashboard: {
    summary: ["dashboard", "summary"] as const,
    recentRuns: ["dashboard", "recentRuns"] as const,
    kpis: ["dashboard", "kpis"] as const,
    attention: ["dashboard", "attention"] as const,
  },
} as const;
