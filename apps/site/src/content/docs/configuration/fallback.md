---
title: Fallback Model
description: Per-provider fallback targets and strict one-hop failover in Runsight.
---

When an LLM provider goes down or returns an error, you do not want your workflow to fail immediately. Runsight's fallback system lets you define a single backup provider and model for each configured provider. If the primary fails, Runsight retries once on the fallback target. There is no chain — one hop, then fail.

## Why per-provider, not global

Early versions of Runsight had a global fallback chain: a ranked list of providers tried in sequence. This was replaced with per-provider fallback targets for three reasons:

1. **Predictability.** A global chain makes it hard to reason about which model will actually run a given soul. With per-provider targets, each provider maps to exactly one fallback — you always know the backup.
2. **Cost control.** A global chain can silently route traffic to an expensive provider. Per-provider mapping gives explicit control over where traffic lands.
3. **No implicit defaults.** The global chain had a "first available" fallback that could pick a provider you did not intend. The current system has no implicit behavior — if no fallback is configured, the call fails.

## How fallback targets work

Each provider can have at most one fallback target, which consists of:

- **Fallback provider** — a different active provider
- **Fallback model** — a specific model available on that provider

The rules are strict:

- A provider **cannot** fall back to itself.
- The fallback provider must be **active** (enabled).
- The fallback model must be in the fallback provider's **discovered model list**.
- Both `fallback_provider_id` and `fallback_model_id` must be set together, or both omitted.

```
OpenAI (gpt-4o) ──fails──> Anthropic (claude-sonnet-4-20250514)     ✓ valid
Anthropic       ──fails──> OpenAI (gpt-4o-mini)                     ✓ valid
Google          ──fails──> (none configured)                        ✓ valid — fails on error
OpenAI          ──fails──> OpenAI (gpt-4-turbo)                     ✗ cannot self-reference
```

## Enabling fallback

Fallback is disabled by default. To turn it on:

1. Open **Settings** and go to the **Fallback** tab.
2. Toggle **Enable fallback** on. This requires at least two active providers.
3. For each provider row, select a fallback provider and then a fallback model from its available models.
4. The selection saves automatically when you pick a model.

The enable/disable toggle is a global switch stored in app settings as `fallback_enabled`. When disabled, all fallback targets are preserved but inactive — no runtime retry occurs.

## What happens at runtime

When a soul's LLM call fails and fallback is enabled:

1. Runsight looks up the soul's `provider` field to find the primary provider.
2. It checks whether that provider has a fallback target configured.
3. If yes, it retries the call once using the fallback provider and model.
4. If the retry also fails, the block fails with the retry error.

If fallback is disabled or no target is configured for the provider, the original error propagates immediately.

:::note
Fallback is **one hop only**. If OpenAI falls back to Anthropic and Anthropic also fails, the call does not chain further to a third provider. This is by design — chains hide failures and make debugging harder.
:::

## How settings are stored

Fallback configuration lives in `.runsight/settings.yaml` alongside other app settings. This file is gitignored.

```yaml title=".runsight/settings.yaml"
fallback_enabled: true
fallback_map:
  - provider_id: openai
    fallback_provider_id: anthropic
    fallback_model_id: claude-sonnet-4-20250514
  - provider_id: anthropic
    fallback_provider_id: openai
    fallback_model_id: gpt-4o-mini
```

Each entry in `fallback_map` is a `FallbackTargetEntry` with three fields:

| Field | Type | Description |
|-------|------|-------------|
| `provider_id` | `str` | The primary provider's ID |
| `fallback_provider_id` | `str` | The backup provider's ID |
| `fallback_model_id` | `str` | The specific model to use on the backup provider |

## Fallback API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/settings/fallbacks` | List all fallback targets for active providers |
| `PUT` | `/settings/fallbacks/{provider_id}` | Set or clear a provider's fallback target |

To clear a fallback target, send both `fallback_provider_id` and `fallback_model_id` as empty strings:

```json
{
  "fallback_provider_id": "",
  "fallback_model_id": ""
}
```

## Soul resolution and fallback

Souls specify their provider via the `provider` field (e.g., `provider: openai`). When a workflow runs:

1. The engine resolves the soul reference via `soul_ref` and looks it up in `custom/souls/`.
2. The soul's `provider` and `model_name` determine which LLM backend handles the call.
3. If the call fails and fallback is enabled, the fallback target for that provider type is used for a single retry.

If a soul does not set a `provider`, it uses the runner's default. Fallback only applies to providers that have an explicit fallback target configured — there is no implicit "pick the next available provider" behavior.

<!-- Linear: RUN-233, RUN-240 — last verified against codebase 2026-04-07 -->
