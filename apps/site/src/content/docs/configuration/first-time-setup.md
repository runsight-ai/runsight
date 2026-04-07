---
title: First-Time Setup
description: Walk through Runsight's onboarding flow — from first launch to your first workflow.
---

import { Steps } from '@astrojs/starlight/components';

This tutorial walks you through what happens when you launch Runsight for the first time. By the end, you will have a configured provider and a workflow open on the canvas.

## Prerequisites

- Runsight installed and running (see [Installation](/docs/getting-started/installation))
- An API key for at least one LLM provider (OpenAI, Anthropic, etc.) — or a local Ollama instance
- Git available in your environment

## What happens on first launch

When Runsight starts, the API server runs a project scaffolding step that prepares your workspace:

<Steps>

1. **Project structure created.** Runsight creates `custom/workflows/` and `custom/souls/` directories, a `.runsight-project` marker file, and a `.gitignore` that excludes `.runsight/` and `.canvas/`.

2. **Git auto-initialized.** If no `.git` directory exists, Runsight runs `git init`, configures a local git user (`runsight@localhost`), stages all scaffolded files, and creates an initial commit with the message "Initial Runsight project".

3. **Settings initialized.** The app settings file `.runsight/settings.yaml` is created with `onboarding_completed: false`. This flag controls whether you see the setup flow or the main dashboard.

</Steps>

## The onboarding flow

<Steps>

1. **Open the app.** Navigate to `http://localhost:5173` (the default Vite dev server port) or the configured host. The setup guard checks `onboarding_completed` in app settings. Since it is `false`, you are redirected to `/setup/start`.

2. **Choose a starting point.** The setup page presents two options:

   - **Tutorial Template** (recommended) — a 3-block workflow called "Research & Review" with a `research` block, a `write_summary` block, and a `quality_review` gate. This uses three soul references (`researcher`, `writer`, `reviewer`) so you can see how blocks chain together.
   - **Blank Canvas** — an empty workflow named "Untitled Workflow" with no blocks. Good if you want to build from scratch using the block palette.

   If you already have providers configured, the template card shows a "Ready to run" badge. Without providers, it shows "Explore mode" — you can still explore the canvas and YAML, but execution requires a provider.

3. **Click "Start Building."** Runsight creates the workflow (without committing to git), sets `onboarding_completed: true`, and navigates you to the canvas editor at `/workflows/{id}/edit`.

4. **Add an API key.** If you chose the template and want to run it, you need a configured provider. You can add one by:
   - Opening **Settings** from the sidebar and clicking **Add Provider**.
   - Or waiting until you hit **Run** — Runsight shows an API key modal that lets you pick a provider, paste your key, and save in one step.

</Steps>

## The API key modal

The API key modal appears in two contexts: during first-time setup if you try to run without a provider, and from the Settings page when adding a new provider. The flow is the same:

1. Select a provider from the dropdown (OpenAI and Anthropic are shown as hero options; others are in a secondary dropdown).
2. Paste your API key. For Ollama, no key is needed — just the base URL.
3. Runsight auto-tests the connection after a 1-second debounce. If the test succeeds, you see a green "Connected" message with the number of available models.
4. Click **Save & Run** (from the canvas modal) or **Save** (from Settings).

The key is stored in `.runsight/secrets.env` as an environment variable (e.g., `OPENAI_API_KEY=sk-...`). The provider YAML file at `custom/providers/` stores a reference like `${OPENAI_API_KEY}`, not the raw key. See [Providers](/docs/configuration/providers) for details on storage.

:::tip
If you have your API key set as a real environment variable (e.g., `export OPENAI_API_KEY=sk-...`), Runsight resolves it from the environment first, before checking the secrets file. You can skip the modal entirely by pre-configuring your environment.
:::

## After onboarding

Once `onboarding_completed` is `true`, the setup guard redirects `/setup/start` back to the main app. Visiting `/setup/start` directly when already onboarded will redirect you to `/`. The reverse is also true — visiting protected routes like `/flows` or `/settings` before completing onboarding redirects you to `/setup/start`.

If the app settings API fails to respond (server down, network error), you are redirected to `/setup/unavailable` — a safety screen that prevents access to protected routes until settings can be loaded. A **Retry** button lets you try again.

## Project directory after setup

After completing first-time setup with the template option, your workspace looks like this:

```
your-project/
├── .git/                    # Auto-initialized git repo
├── .gitignore               # Excludes .runsight/ and .canvas/
├── .runsight-project        # Project marker file
├── .runsight/               # Gitignored runtime data
│   ├── settings.yaml        # App settings (onboarding_completed, fallback_enabled)
│   └── secrets.env          # API keys (gitignored)
└── custom/
    ├── providers/
    │   └── openai.yaml      # Created when you add a provider
    ├── souls/               # Empty until you create souls
    └── workflows/
        └── research-review.yaml  # The template workflow
```

## Next steps

- [Providers](/docs/configuration/providers) — add more providers and manage API keys
- [Quickstart](/docs/getting-started/quickstart) — run your first workflow
- [YAML Schema](/docs/workflows/yaml-schema) — understand the workflow YAML format

<!-- Linear: RUN-352, RUN-738 — last verified against codebase 2026-04-07 -->
