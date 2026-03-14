# Research & Architecture Skill (Observatory)

This skill dictates how AI agents should conduct research, formulate architectural decisions, and document their findings before writing any code.

## 1. Storage & File Structure (The Observatory)
All research, competitor analysis, and architectural specifications MUST be stored in the `observatory/` directory at the root of the project.
- **Path format:** `observatory/projects/<project-name>/`
- **Required files:** 
  - `RESEARCH.md` (Competitor analysis and technical feasibility)
  - `ARCH.md` (Technical architecture, component trees, data flow)
  - `SPEC.md` (Product specification, user stories, milestones)

## 2. Using Codebones for Research
Do NOT blindly read massive codebases. You MUST use the `codebones` CLI tool to save tokens and avoid hallucination.
- **Generate Skeletons:** Run `codebones pack --no-files . > repo-skeleton.xml` in competitor repositories to get a highly compressed architectural map.
- **Read Skeletons:** Parse the `repo-skeleton.xml` to understand where state management, graph logic, or core APIs live.
- **Drill Down:** Only use the `Read` tool on specific files *after* you have identified them from the skeleton.

## 3. Repository Structure Context
When proposing architectures, you must align with the existing `runsight` monorepo structure:
- `apps/gui/`: React/Vite/Zustand frontend.
- `apps/api/`: FastAPI/Python backend engine.
- `libs/core/`: Python execution engine and block definitions.
- `observatory/`: Strategic planning, research, and documentation.
- `.cursor/skills/`: AI agent instructions and workflows.

## 4. Depth of Research & Architecture
Your architectural proposals must be exhaustive but concise:
- **Compare & Steal:** Always analyze at least 2-3 open-source competitors (e.g., in `~/Documents/github/competitor-repos/`). Note their canvas libraries, state managers, and data structures.
- **State & Data Flow:** Explicitly define how data moves (e.g., "Zustand store -> React Flow nodes -> flat JSON serialization -> FastAPI endpoint").
- **UI/UX Confidence:** Before touching the frontend, verify if existing mockups or briefs exist (often found in `.agora/` or `observatory/`). If the current UI is broken, propose a systematic refactor or rewrite rather than patching bugs blindly.

## 5. Linear Sync & Git Persistence
Research on disk is ephemeral if not tracked.
1. **Linear:** Every `SPEC.md` and `ARCH.md` must be translated into **Projects, Epics, and Tickets** using the `user-Linear` MCP server. Follow the strict 3-5 bullet point rule defined in the Linear management skill.
2. **Git:** You must commit all files generated in `observatory/` to version control immediately so the state is never lost.
