# Research & Architecture Skill

This skill dictates how AI agents should conduct research, formulate architectural decisions, and document findings. The final destination of all actionable specs is **Linear** — not files on disk.

## 1. The Observatory (Intermediate Storage)
The `observatory` repo (`/Users/nataly/Documents/github/observatory/`) is for **raw and intermediate artifacts only** — things that don't belong in Linear but are useful reference material for agents.
- **What belongs here:** Raw competitor analysis, mockup HTML/CSS files, team configs, product research notes, design components, intermediate drafts.
- **What does NOT belong here:** Final specs, architecture docs, or anything that should be actionable. Those go directly into Linear Project/Epic/Ticket descriptions.
- **Key directories:**
  - `mockups/` — HTML/CSS designs for UI flows. Use as visual reference for UI tickets.
  - `research/` — Raw competitor analysis, market research.
  - `design/` — Design components and assets.
  - `SKILLS/` — Various AI agent skills.
  - `teams/` — Team configs.

## 2. Using Codebones for Research
Do NOT blindly read massive codebases. Use the `codebones` CLI tool to save tokens.
- **`codebones pack --no-files .`**: Generates a lightweight structural skeleton of an entire repo. Use for high-level orientation.
- **`codebones outline <path>`**: Prints file tree or structural skeleton of a specific file (class/function signatures). Use to understand structure without reading full source.
- **`codebones search <query>`**: Full-text search across the repo index. Use to find specific patterns, function names, or concepts.
- **`codebones get <path_or_symbol>`**: Retrieves full source code for a specific file or symbol. Use only when you know exactly what you need.

**Recommended workflow:** `outline` first to orient, `search` to find specifics, `get` only for the exact code you need.

## 3. Competitor Repos
All competitor repos are cloned at `~/Documents/github/competitor-repos/`. Each repo has a pre-generated `repo-skeleton.xml` file that agents should use as a navigational map before diving into source code.

Available repos:
| Repo | Category |
|------|----------|
| `n8n` | Visual workflow builder (node-based, JSON) |
| `Flowise` | Visual LLM chain builder (drag-and-drop, JSON) |
| `dify` | LLM app builder with visual workflows |
| `kestra` | Declarative workflow orchestration (YAML-based) |
| `langflow` | Visual LangChain builder |
| `ComfyUI` | Node-based image generation pipelines |
| `airflow` | DAG-based workflow orchestration (Python) |
| `argo-workflows` | Kubernetes-native workflow engine (YAML) |
| `temporal` | Durable execution / workflow engine |
| `terraform` | Declarative infrastructure as code (HCL) |
| `langfuse` | LLM observability and tracing |
| `agenthelm` | AI agent orchestration framework |
| `SWE-AF` | SWE agent framework |
| `openclaw` | Open-source agent platform |

**How to use:** Run `codebones outline` or `codebones search` inside a competitor's directory. Use `repo-skeleton.xml` as the structural map. Do not read entire codebases.

## 4. Runsight Monorepo Structure
When proposing architectures, align with the existing structure:
- `apps/gui/` — React/Vite/Zustand frontend
- `apps/api/` — FastAPI/Python backend engine
- `libs/core/` — Python execution engine and block definitions
- `.cursor/skills/` — AI agent instructions and workflows

## 5. Depth of Research
Architectural proposals must be exhaustive but concise:
- **Compare & Steal:** Analyze at least 2-3 open-source competitors. Note their libraries, state managers, data structures, and UX patterns. Pick the best and adapt.
- **UI/UX Ground Truth:** Before proposing UI work, check existing mockups in `observatory/mockups/`. Use them as visual reference alongside competitor DOM structures.

## 6. Final Destination: Linear
All research findings must be synthesized and placed **directly into the provided Linear tickets**. 
- **Do not invent your own tickets.** You will be given specific ticket IDs to populate.
- **No scattered files.** Do not create `SPEC.md`, `ARCH.md`, or `UI_UX_SPEC.md` files as final outputs. Observatory is for intermediate work only.
- **Ticket exhaustiveness.** Every detail required to build the feature must end up in the Linear issue description.
