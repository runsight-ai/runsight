---
title: Providers
description: How to add and manage LLM providers in Runsight — OpenAI, Anthropic, Google, and more.
---

Providers are the LLM backends that power your workflows. Each provider represents a connection to an AI service — OpenAI, Anthropic, Google, Ollama, or any OpenAI-compatible endpoint. Before you can run a workflow, at least one provider must be configured with a valid API key.

## Supported providers

Runsight supports the following providers out of the box:

| Provider | Type key | Models | API key required |
|----------|----------|--------|-----------------|
| OpenAI | `openai` | GPT-4o, GPT-4, o-series | Yes |
| Anthropic | `anthropic` | Claude Haiku, Sonnet, Opus | Yes |
| Google | `google` | Gemini Pro, Gemini Flash | Yes |
| Azure OpenAI | `azure_openai` | GPT models via Azure | Yes |
| AWS Bedrock | `aws_bedrock` | Claude, Titan via AWS | Yes |
| Mistral | `mistral` | Mistral Large, Codestral | Yes |
| Cohere | `cohere` | Command R+, Embed | Yes |
| Groq | `groq` | LLaMA, Mixtral (fast inference) | Yes |
| Together AI | `together` | Open-source models | Yes |
| Ollama | `ollama` | Local models (LLaMA, etc.) | No |
| Custom | `custom` | Any OpenAI-compatible endpoint | Yes |

Provider type is inferred from the name when you create a provider. For example, a provider named "OpenAI Production" is automatically assigned the type `openai`.

## Adding a provider via the Settings page

1. Open **Settings** from the sidebar.
2. On the **Providers** tab, click **Add Provider**.
3. In the dialog, select a provider from the dropdown.
4. Enter your API key. Runsight auto-tests the connection after a short debounce.
5. For Ollama or custom providers, enter a **Base URL** (Ollama defaults to `http://localhost:11434`).
6. Once the connection test shows success, click **Save**.

After saving, Runsight tests the connection again and populates the provider's model list from the remote API.

:::tip
You can also add a provider during your first run. If no providers are configured when you try to execute a workflow, Runsight shows an API key modal so you can set one up on the spot.
:::

## How providers are stored

Providers are persisted as individual YAML files in `custom/providers/`. The provider ID is the slugified name — for example, a provider named "OpenAI" is stored at `custom/providers/openai.yaml`.

```yaml title="custom/providers/openai.yaml"
name: OpenAI
type: openai
api_key: ${OPENAI_API_KEY}
base_url: null
status: connected
is_active: true
models:
  - gpt-4o
  - gpt-4o-mini
  - gpt-4-turbo
```

API keys are stored as environment variable references (`${PROVIDER_API_KEY}`) pointing to entries in `.runsight/secrets.env`. The secrets file is gitignored and never committed. You can also reference real environment variables — `os.environ` takes precedence over the secrets file.

## How souls reference providers

Every soul **must** set both `provider` and `model_name`. The soul schema marks these fields as optional, but the runner hard-fails at execution time if either is missing:

- Neither set → `ValueError: "Soul '{id}' must define an explicit provider and model_name"`
- `model_name` set but no `provider` → `ValueError: "Soul '{id}' must define an explicit provider"`
- `provider` set but no `model_name` → `ValueError: "Soul '{id}' must define an explicit model_name"`

There is no global fallback or default provider. If you see a soul without these fields, it will fail on run.

```yaml title="custom/souls/researcher.yaml"
version: '1.0'
soul:
  id: researcher
  role: Senior Researcher
  system_prompt: "Research the given topic thoroughly."
  provider: openai
  model_name: gpt-4o
  temperature: 0.7
```

The `provider` field value must match the `type` of a configured provider (e.g., `openai`, `anthropic`, `google`), not the provider's display name or ID.

## Model catalog

Runsight includes a built-in model catalog powered by LiteLLM's model cost dictionary. The catalog provides metadata for every known model across all providers:

- Model ID and provider
- Max tokens and max input tokens
- Input and output cost per token
- Capability flags: vision support, function calling support, streaming support

By default, the `/models` API endpoint returns only models whose provider matches a configured provider. Pass `?all=true` to see the full catalog regardless of configuration.

## Provider API endpoints

All provider endpoints live under `/settings/providers`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/settings/providers` | List all providers |
| `GET` | `/settings/providers/{id}` | Get a single provider |
| `POST` | `/settings/providers` | Create a provider |
| `PUT` | `/settings/providers/{id}` | Update a provider |
| `DELETE` | `/settings/providers/{id}` | Delete a provider |
| `POST` | `/settings/providers/{id}/test` | Test a saved provider's connection |
| `POST` | `/settings/providers/test` | Test credentials before saving |

The model catalog has its own endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/models` | List models (filtered to configured providers by default) |
| `GET` | `/models/providers` | List provider summaries with `is_configured` flag |

## Managing providers

### Testing a connection

Click **Test** on any provider row in the Providers tab. The test hits the provider's model-listing endpoint and reports success or failure along with latency. On success, the provider's model list is refreshed.

### Enabling and disabling

Each provider has an **Enabled** toggle. Disabled providers are excluded from model catalog queries and fallback target lists but are not deleted — you can re-enable them at any time.

### Editing

Click **Edit** on a provider row to update the API key or base URL. Leave the API key field empty to keep the existing key.

### Deleting

Click **Delete** to remove a provider. This deletes the YAML file from `custom/providers/` and removes the API key from `.runsight/secrets.env`.

:::caution
Deleting a provider that souls reference by type will cause those souls to fail at runtime. Check soul files before deleting a provider.
:::

<!-- Linear: RUN-151, RUN-233 — last verified against codebase 2026-04-07 -->
