---
title: Settings
description: Reference for the settings.yaml file and the settings API.
---

Application settings are stored in `.runsight/settings.yaml`. This file is created automatically during [project scaffolding](/docs/configuration/first-time-setup) and is gitignored.

## Settings fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `onboarding_completed` | `bool` | `false` | Whether the first-time setup flow has been completed. Controls whether the app redirects to the setup screen. |
| `fallback_enabled` | `bool` | `false` | Whether runtime fallback is active. See [Fallback](/docs/configuration/fallback). |
| `auto_save` | `bool \| null` | `null` | Auto-save preference (reserved for future use). |

## Fallback map

The same file stores per-provider fallback targets under a `fallback_map` key:

```yaml title=".runsight/settings.yaml"
onboarding_completed: true
fallback_enabled: true
fallback_map:
  - provider_id: anthropic
    fallback_provider_id: openai
    fallback_model_id: gpt-4.1-mini
```

Each entry in `fallback_map` has three fields:

| Field | Type | Description |
|-------|------|-------------|
| `provider_id` | `str` | The provider this fallback applies to |
| `fallback_provider_id` | `str` | The provider to fall back to |
| `fallback_model_id` | `str` | The specific model to use on the fallback provider |

See [Fallback](/docs/configuration/fallback) for how to configure fallback targets.

## Storage locations

| Data | Location | Git tracked |
|------|----------|-------------|
| Providers | `custom/providers/*.yaml` | Yes |
| API keys | `.runsight/secrets.env` | No (gitignored) |
| App settings and fallback map | `.runsight/settings.yaml` | No (gitignored) |

Provider YAML files live inside `custom/providers/` and are committed to git. API keys are stored as environment variable references (`${OPENAI_API_KEY}`) that resolve against the real environment first, then `.runsight/secrets.env`. See [Providers](/docs/configuration/providers) for details.

## Settings API endpoints

### App settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/settings/app` | Get current app settings |
| `PUT` | `/settings/app` | Update app settings (partial merge) |

### Providers

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/settings/providers` | List all providers |
| `GET` | `/settings/providers/{id}` | Get a single provider |
| `POST` | `/settings/providers` | Create a provider |
| `PUT` | `/settings/providers/{id}` | Update a provider |
| `DELETE` | `/settings/providers/{id}` | Delete a provider |
| `POST` | `/settings/providers/{id}/test` | Test a saved provider connection |
| `POST` | `/settings/providers/test` | Test credentials before saving |

### Fallback

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/settings/fallbacks` | List fallback targets for all active providers |
| `PUT` | `/settings/fallbacks/{provider_id}` | Set or clear a provider's fallback target |

### Budgets

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/settings/budgets` | List budgets (placeholder -- returns an empty list) |

<!-- Linear: RUN-151, RUN-233, RUN-240 — last verified against codebase 2026-04-07 -->
