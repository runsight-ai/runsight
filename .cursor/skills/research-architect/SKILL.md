# Research & Architecture Skill (Observatory)

This skill dictates how AI agents should conduct research, formulate architectural decisions, and document their findings before writing any code.

## 1. Storage & File Structure (The Observatory)
All research, competitor analysis, and architectural specifications MUST be stored in the separate `observatory` repository located at `/Users/nataly/Documents/github/observatory/`. Do not create an observatory folder inside the runsight repo.
- **Path format:**
  - `/Users/nataly/Documents/github/observatory/research/<topic>.md` (Competitor analysis and technical feasibility)
  - `/Users/nataly/Documents/github/observatory/specs/<project-name>/ARCH.md` (Technical architecture, component trees, data flow)
  - `/Users/nataly/Documents/github/observatory/specs/<project-name>/SPEC.md` (Product specification, user stories, milestones)

## 2. Using Codebones for Research
Do NOT blindly read massive codebases. You MUST use the `codebones` CLI tool to save tokens and avoid hallucination.
- **`codebones pack --no-files .`**: Generates a lightweight skeleton of an entire repo. Great for initial high-level context or storing in the observatory.
- **`codebones outline <path>`**: Prints the file tree or the structural skeleton of a specific file. Use this to understand class/function signatures without reading the whole file.
- **`codebones search <query>`**: Searches across the entire repository using its FTS5 index. Use this to find specific patterns (e.g. `codebones search reactflow`).
- **`codebones get <path_or_symbol>`**: Retrieves the full source code for a specific file or symbol once you know exactly what you are looking for.

## 3. Repository Structure Context
When proposing architectures, you must align with the existing monorepo structure:
- **`runsight` repo (`/Users/nataly/Documents/github/runsight/`)**:
  - `apps/gui/`: React/Vite/Zustand frontend.
  - `apps/api/`: FastAPI/Python backend engine.
  - `libs/core/`: Python execution engine and block definitions.
  - `.cursor/skills/`: AI agent instructions and workflows.
- **`observatory` repo (`/Users/nataly/Documents/github/observatory/`)**:
  - `mockups/`: HTML/CSS designs for UI flows (e.g. `flow-2-create-run-pm`). Use these as the source of truth for UI/UX!
  - `research/`: Market research and competitor analysis.
  - `specs/`: Architecture and product specs.
  - `design/`: Design components.
  - `SKILLS/`: Various AI agent skills.

## 4. Depth of Research & Architecture
Your architectural proposals must be exhaustive but concise:
- **Compare & Steal:** Always analyze at least 2-3 open-source competitors (e.g., in `~/Documents/github/competitor-repos/`). Note their canvas libraries, state managers, and data structures. Pick the best patterns and adapt them.
- **UI/UX Ground Truth:** Before touching the frontend, you MUST check the existing UI flows and screen maps in `/Users/nataly/Documents/github/observatory/mockups/`. If the current UI code is broken or ugly, put it on a separate branch (treat it as legacy) and rewrite it cleanly following the approved mockups and competitor patterns. Do not blindly patch spaghetti code.

## 5. All Research Goes Into Provided Tickets
No information exists outside of Linear. If a detail (Spec, Arch, DoD, AC, Visual Spec, DOM structure) is not in a Linear ticket, it does not exist. 
- **Target Provided Tickets:** You must place all research findings directly into the existing, provided Linear tickets. Do not invent your own tickets.
- **No Scattered Files:** Do not create random markdown files or `UI_UX_SPEC.md` documents expecting agents to read them later. 
- **Ticket Exhaustiveness:** Every single detail required to build the feature must be copy-pasted or synthesized directly into the Linear issue description.
