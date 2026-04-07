---
title: Soul Library
description: Managing souls in the GUI — browsing, creating, editing, and deleting agent identities.
---

The Soul Library is the visual management surface for souls. It lives at `/souls` in the Runsight GUI and provides a searchable, sortable table of all soul files in `custom/souls/`. From the library, you can create new souls, edit existing ones, and delete souls with dependency awareness.

## Browsing the library

The Soul Library page displays all souls in a data table with six columns:

| Column | What it shows |
|--------|--------------|
| **Name** | The soul's `role` field, with an avatar circle showing the first letter and the soul's `avatar_color`. A warning icon appears if the `system_prompt` is empty. |
| **Model** | The `model_name` value (e.g., `gpt-4o`). Shows a dash if not set. |
| **Provider** | The `provider` value. Shows a warning if the provider is disabled in Settings. |
| **Tools** | Badge chips for each tool the soul declares (excluding `delegate`, which is hidden). Each badge shows the tool name and metadata labels for origin and executor when relevant. |
| **Used In** | The number of workflows that reference this soul via `soul_ref`. |
| **Modified** | Relative time since the soul was last saved (e.g., "2h ago", "3d ago"). |

The table supports **client-side search** (filters by name) and **column sorting** (click any sortable column header). Clicking a row navigates to the edit form.

## Creating a soul

1. Click the **New Soul** button in the top-right corner of the library page. This navigates to `/souls/new`.

2. Fill in the form. The form is organized into five sections:

   **Identity** — The soul's display name (maps to the `role` field in YAML) and avatar color. The name field is required.

   **Model** — Provider and model dropdowns. The provider dropdown shows all active providers from Settings. Selecting a provider populates the model dropdown with that provider's available models. If no providers are configured, the dropdown is disabled with a message to add one in Settings.

   **Prompt** — A large text area for the `system_prompt`. This is the core behavioral definition of the soul. The field is required — an empty prompt shows a warning in the library table.

   **Tools** — A collapsible section (collapsed by default) showing all available tools as toggle cards. Each card displays the tool name, description, origin (Built-in or Custom), and executor type (Native, Python, or Request). Click a card to enable or disable the tool on this soul.

   **Advanced** — A collapsible section (collapsed by default) containing:
   - **Temperature** — a slider from 0.0 to 2.0, defaulting to 0.7
   - **Max Tokens** — a number input, empty by default (uses model default)
   - **Max Tool Iterations** — a number input, defaulting to 5

3. Click **Create Soul**. The API writes a YAML file to `custom/souls/` and auto-commits it to Git. You are returned to the library page.

:::note
The form requires both a name and a system prompt to enable the submit button. Provider and model are not required to save — you can create a soul definition and configure its model later.
:::

## Editing a soul

Click any row in the library table to open the edit form at `/souls/:id/edit`. The form is pre-filled with the soul's current values.

The same five sections (Identity, Model, Prompt, Tools, Advanced) are available. Modify any field, then click **Save Changes**. The API updates the YAML file and auto-commits to Git.

The **Save Changes** button is disabled until you modify at least one field. If you navigate away with unsaved changes, a confirmation dialog asks whether to discard or keep editing.

### Canvas return flow

When editing a soul from the workflow canvas (via the soul picker's "Create new soul" link), the URL includes a `?return=` parameter. In this mode, the save button reads **Save & Return to Canvas** and navigates back to the canvas after saving.

## Deleting a soul

Deleting a soul involves a dependency check. When you open the delete dialog, the UI fetches `GET /api/souls/:id/usages` to determine which workflows reference this soul.

**No dependencies:** The dialog shows a simple confirmation: "Are you sure you want to delete [soul name]? This action cannot be undone."

**Has dependencies:** The dialog shows a warning: "This soul is currently used in active workflows." Below the warning, it lists the total count and shows workflow name badges for up to five affected workflows. If more than five workflows are affected, a "+N more" badge appears.

In both cases, clicking **Delete** (or **Delete anyway** when dependencies exist) removes the soul's YAML file and auto-commits the deletion to Git. The operation uses `force: true` — it does not block on dependencies. The dependency warning is informational, giving you the chance to update affected workflows first.

:::caution
Deleting a soul that is referenced by workflows will cause those workflows to fail at parse time. The parser raises a `ValueError` when it cannot resolve a `soul_ref` to a soul file.
:::

## Avatar color picker

The Identity section includes a color picker with six preset options. These map to design system tokens:

| Value | Description |
|-------|-------------|
| `accent` | The default. Uses the primary accent color. |
| `info` | Blue informational tone. |
| `success` | Green success tone. |
| `warning` | Yellow/amber warning tone. |
| `danger` | Red danger tone. |
| `neutral` | Gray neutral tone. |

The selected color is stored in the `avatar_color` field of the soul's YAML file and displayed as the avatar circle in the library table.

## How the library reads souls

The Soul Library page calls `GET /api/souls`, which scans all `.yaml` files in `custom/souls/`. For each soul, the API also scans all workflow files to count `soul_ref` references, populating the `workflow_count` field. The `modified_at` timestamp is set by the API when a soul is created or updated through the GUI.

This scan-based approach means the library always reflects the current state of the filesystem. If you add or modify a soul file directly (outside the GUI), the changes appear on the next page load.

## What's next

- [Soul Files](/docs/souls/soul-files) — complete field reference for soul YAML files
- [Inline Souls](/docs/souls/inline-souls) — defining souls directly inside workflow YAML
- [Souls Overview](/docs/souls/overview) — concepts and architecture

<!-- Linear: RUN-467, RUN-437, RUN-443, RUN-575 — Soul Management project (bb749057) — last verified against codebase 2026-04-07 -->
