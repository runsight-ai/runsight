# Linear Product Management & Sizing Skill

When managing the Runsight roadmap in Linear, we follow a strict, top-down, value-driven hierarchy. **Never create granular tickets (issues) until the high-level Initiative and Project structure is fully defined and approved by the user.**

## The Sizing Hierarchy

### 1. Initiative (Business Impact / Core Value Prop)
- **What it is:** A massive, cross-cutting goal that drives the business forward or represents a core value proposition (e.g., "Mission Control & Observability", "Enterprise Readiness", "Agentic Capabilities").
- **Linear Object:** `Initiative`
- **Rule:** Initiatives are thematic, NOT chronological. Do not put numbers or priorities in their names.
- **Description Requirements:** Must use the following Markdown template to ensure strategic alignment:

  ```markdown
  ## 📖 Context / The Problem
  *What is the market gap or user pain point?*

  ## 🤔 The "Why"
  *Why is this critical to the business? Why prioritize this over other things?*

  ## 👥 Target Audience
  *(Optional) Who specifically are we solving this for? (e.g., Solo devs, Enterprise CTOs, AI Engineers).*

  ## 💡 The "What"
  *The high-level solution or product offering we are building to address the problem.*

  ## 🎯 Objectives & Goals
  *What does success look like qualitatively?*

  ## 📈 Success Metrics (KPIs)
  *(Optional) How will we objectively measure success? (e.g., "100 active daily workflows", "0% budget overruns").*

  ## 🚧 Scope
  - **In Scope:** *Broad boundaries of what is included.*
  - **Out of Scope:** *What is explicitly excluded at this high level.*

  ## ⚠️ Dependencies & Risks
  *Biggest threats to this massive goal, or external systems/teams we rely on.*
  ```

### 2. Project (Major Feature)
- **What it is:** A large, distinct feature or product area that takes weeks to build (e.g., "Role-Based Access Control", "Visual Workflow Canvas", "Trigger Engine").
- **Linear Object:** `Project` (Use `save_project` MCP tool, must include `addInitiatives`).
- **Description Requirements:** The Project description MUST act as the ultimate source of truth. It must contain the comprehensive Product Spec and Technical Architecture (Spec + Arch always on project level). Every Project must use the following Markdown template:

  ```markdown
  ## 📖 Product Spec
  - **Overview & Context:** Problem statement, business value.
  - **Goals & Non-goals:** Primary objectives and explicit exclusions.
  - **Target Users & Use Cases:** Who is this for and how will they use it?
  - **Scope:** In Scope vs Out of Scope.
  - **User Flow & UX Target:** Step-by-step flow and design inspiration (e.g. "n8n style").

  ## 🏛️ ADR (Architecture Decision Record)
  - **Decision:** Major design decisions and rationale.
  - **Context:** Why this approach over alternatives? (e.g. YAML vs JSON state).
  - **Consequences:** Trade-offs and impact on the system.

  ## 🛠️ HLD (High-Level Design)
  - **System Components:** Stack and component boundaries.
  - **Data Entities:** High-level domain objects and state transitions.
  - **APIs & Integrations:** Key interfaces between systems.
  - **Security & Scalability:** Risks and constraints.

  ## 📦 Deliverables & Milestones
  - **Milestone 1:** [Name] – [Description]
  - next milestone...
  ```

### 3. Milestone (Deliverable with Product Value)
- **What it is:** A checkpoint *within* a project that represents a shippable increment of product value (e.g., Inside the "Trigger Engine" project, Milestone 1 is "Webhooks", Milestone 2 is "Cron").
- **Linear Object:** `Project Milestone` (Use `save_milestone` MCP tool).

### 4. Epic (Technical Milestone)
- **What it is:** A grouping of technical tasks needed to achieve a milestone (e.g., "Build CRUD API for Workflows"). Epics can stretch across multiple milestones.
- **Linear Object:** `Parent Issue` (An issue that contains sub-issues).
- **Formatting Rules:** Use concise bullet points instead of paragraphs. Limit each section to 3-5 key points (per section, not in total). Use shorthand notation where appropriate (e.g., "req." for "requirements").
- **Description Requirements:** Epics must be treated as a mini architectural document. It must cover ALL technical aspects of what it is touching based on the project-level architecture. **Crucially, Epics MUST include explicit API Endpoints** (routes, methods, request/response contracts) if they involve backend communication, along with a clear overview of sub-tickets.

### 5. Ticket (Atomic Unit of Work)
- **What it is:** A single Pull Request. A specific API endpoint, a UI component, or a test suite.
- **Linear Object:** `Issue` (Use `save_issue` MCP tool).
- **Formatting Rules:** Use concise bullet points instead of paragraphs. Limit each section to 3-5 key points (per section). Use shorthand notation where appropriate. Include only essential headers.
- **Description Requirements:** Strictly technical. Must contain super detailed Implementation Details, **Exact Data Models** (database schemas, TypeScript interfaces, Python Pydantic models), Definition of Done (DoD), and Acceptance Criteria (AC). For visual tickets, the DoD and AC must be extremely rigorous regarding look and feel to prevent broken UX. All implementation details must be at the ticket level, not scattered in standalone files.

## Operating Procedure
1. **Always plan top-down.** Start by defining the thematic Initiatives with full context.
2. **Break Initiatives into Projects.** Ensure every Project has a clear description of the feature and scope.
3. **Wait for approval.** Do not generate Issues/Tickets until the user explicitly approves the Project landscape.
4. **Create or Re-use the Skeleton Structure First:** If a skeleton structure already exists, REUSE existing tickets instead of constantly canceling them. If starting from scratch, create the Epics, Milestones, and Tickets with *minimal placeholder details* to establish the hierarchy in Linear.
5. **Research & Populate:** ONLY AFTER the skeleton is in place, spin up specialized research/architect agents *per ticket* or *per epic* to read competitor code, mockups, and existing code to fill in the *exact* Implementation Details, DoD, and Visual AC directly into those pre-existing provided tickets. Never let agents invent their own chaotic ticket hierarchies from scratch.
6. **Split if Needed:** If an agent discovers during research that a ticket is too large, it may split the atomic ticket into two.
