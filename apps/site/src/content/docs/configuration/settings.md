---
title: Settings
description: Reference for the Runsight Settings page — Providers tab, Fallback tab, and app settings API.
---

The Settings page is accessible from the sidebar at `/settings`. It contains two tabs: **Providers** and **Fallback**.

## Providers tab

The Providers tab displays a table of all configured LLM providers. Each row shows:

| Column | Description |
|--------|-------------|
| **Provider** | Name and optional base URL, with a color-coded avatar showing the provider's initials |
| **API Key** | A masked preview of the stored key (e.g., `sk-pro...Ab3f`), an env var reference, or "(none configured)" |
| **Status** | Connection status dot — green (Connected), yellow (Rate limited), red (Error), gray (Unknown) |
| **Models** | Count of discovered models (e.g., "42 models") |
| **Actions** | Enable/disable toggle, Test, Edit, and Delete buttons |

### Empty state

When no providers are configured, the tab shows an empty state with the message "No providers configured" and an **Add Provider** button.

### Error state

If the provider list fails to load (e.g., API server unreachable), a retry panel is shown with the error message and a **Retry** button.

### Add Provider button

The **Add Provider** button in the page header opens the provider dialog. This button is only visible when the Providers tab is active.

## Fallback tab

The Fallback tab manages per-provider fallback targets. See [Fallback Model](/docs/configuration/fallback) for the full explanation of the fallback system.

The tab contains:

- **Enable fallback** toggle — a global on/off switch. Requires at least two active providers. When fewer than two providers are active, the toggle is disabled and a message reads "Enable at least two providers to configure runtime fallback."
- **Fallback target rows** — one row per active provider, each with:
  - Provider name (read-only)
  - Fallback provider dropdown (excludes the provider itself)
  - Fallback model dropdown (populated from the selected fallback provider's discovered models)
  - Clear button to remove the fallback target

When fallback is disabled, the rows are visually dimmed and non-interactive, but configured targets are preserved.

## App settings

General application settings are stored separately from providers and fallback targets.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `onboarding_completed` | `bool` | `false` | Whether the first-time setup flow has been completed |
| `fallback_enabled` | `bool` | `false` | Whether runtime fallback is active |
| `auto_save` | `bool \| null` | `null` | Auto-save preference (reserved for future use) |

## Storage

Settings are stored in two locations:

| Data | Location | Git tracked |
|------|----------|-------------|
| Providers | `custom/providers/*.yaml` | Yes |
| API keys | `.runsight/secrets.env` | No (gitignored) |
| App settings & fallback map | `.runsight/settings.yaml` | No (gitignored) |

Provider YAML files live inside the `custom/` directory and are committed to git. This means provider names, types, and base URLs are version-controlled, but API keys are not — they are stored as `${ENV_VAR}` references that resolve against `.runsight/secrets.env` or the real environment.

The `.runsight/` directory is created automatically and added to `.gitignore` during project scaffolding.

## Settings API endpoints

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

### App settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/settings/app` | Get current app settings |
| `PUT` | `/settings/app` | Update app settings (partial merge) |

### Budgets

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/settings/budgets` | List budgets (currently returns an empty list — frontend not yet built) |

### Provider response schema

The `SettingsProviderResponse` returned by provider endpoints contains:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Provider ID (slugified name, derived from filename) |
| `name` | `str` | Display name |
| `type` | `str \| null` | Provider type (e.g., `openai`, `anthropic`) |
| `status` | `str` | Connection status: `connected`, `error`, or `unknown` |
| `is_active` | `bool` | Whether the provider is enabled (default: `true`) |
| `api_key_env` | `str \| null` | Env var reference (e.g., `${OPENAI_API_KEY}`) |
| `api_key_preview` | `str \| null` | Masked preview of the resolved key |
| `base_url` | `str \| null` | Custom endpoint URL |
| `models` | `list[str]` | Discovered model IDs |
| `model_count` | `int` | Number of discovered models |
| `created_at` | `str \| null` | Creation timestamp |
| `updated_at` | `str \| null` | Last update timestamp |

<!-- Linear: RUN-151, RUN-233, RUN-240 — last verified against codebase 2026-04-07 -->
