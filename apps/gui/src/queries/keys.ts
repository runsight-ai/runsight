export const queryKeys = {
  workflows: {
    all: ["workflows"] as const,
    detail: (id: string) => ["workflows", id] as const,
  },
  runs: {
    all: ["runs"] as const,
    detail: (id: string) => ["runs", id] as const,
    logs: (id: string) => ["runs", id, "logs"] as const,
  },
  souls: {
    all: ["souls"] as const,
    detail: (id: string) => ["souls", id] as const,
  },
  steps: {
    all: ["steps"] as const,
    detail: (id: string) => ["steps", id] as const,
  },
  tasks: {
    all: ["tasks"] as const,
    detail: (id: string) => ["tasks", id] as const,
  },
  settings: {
    all: ["settings"] as const,
    providers: ["settings", "providers"] as const,
    provider: (id: string) => ["settings", "providers", id] as const,
    models: ["settings", "models"] as const,
    modelDefaults: ["settings", "modelDefaults"] as const,
    budgets: ["settings", "budgets"] as const,
    appSettings: ["settings", "appSettings"] as const,
    fallback: ["settings", "fallback"] as const,
  },
  git: {
    status: ["git", "status"] as const,
    log: ["git", "log"] as const,
  },
  dashboard: {
    summary: ["dashboard", "summary"] as const,
    recentRuns: ["dashboard", "recentRuns"] as const,
  },
} as const;
