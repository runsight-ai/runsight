# Linear Product Management & Sizing Skill

When managing the Runsight roadmap in Linear, we follow a strict, top-down, value-driven hierarchy. **Never create granular tickets (issues) until the high-level Initiative and Project structure is fully defined and approved by the user.**

## The Sizing Hierarchy

### 1. Initiative (Business Impact / Core Value Prop)
- **What it is:** A massive, cross-cutting goal that drives the business forward or represents a core value proposition (e.g., "Mission Control & Observability", "Enterprise Readiness", "Agentic Capabilities").
- **Linear Object:** `Initiative`
- **Rule:** Initiatives are thematic, NOT chronological. Do not put numbers or priorities in their names.
- **Description Requirements:** Must use the following Markdown template:

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
- **Description Requirements:** The Project description MUST act as the ultimate source of truth. It contains three mandatory documents: **Product Spec**, **ADR**, and **HLD**. Every Project must use the following Markdown template:

  ```markdown
  # 📖 Product Spec

  ## Overview & Context
  - Problem statement
  - Why this matters now
  - Business value

  ## 🎯 Goals & Success Metrics
  - Primary objectives
  - Key measurable outcomes (KPIs)
  - Non-goals (to avoid scope creep)

  ## 👥 Users & Use Cases
  - Primary user personas
  - Core use cases
  - Key workflows enabled

  ## 🚧 Scope
  - **In Scope**
  - **Out of Scope**

  ## 📋 Product Requirements
  - Core functional requirements
  - Edge cases & Constraints

  ## 🔄 User Flow & Experience
  1. Entry point
  2. Core interaction flow
  3. Completion / outcome
  4. Error states

  ## 🎨 UX Inspiration & Design Language
  - Competitor references (e.g. "n8n style nodes")
  - Design system rules (e.g. "strict CSS variables only")

  ---
  # 🏛️ ADR (Architecture Decision Records)

  ### ADR-1: [Decision Title]
  - **Decision:** What we chose.
  - **Context:** What alternatives were considered and why they were rejected.
  - **Consequences:** Trade-offs, what we gain, what we lose.

  *(Repeat for each major decision)*

  ---
  # 🛠️ HLD (High-Level Design)

  ## System Components & Boundaries
  - Stack, services, libraries
  - Service boundaries

  ## 🧩 Data Entities & State Transitions
  - High-level domain objects
  - Relationships
  - State transitions

  ## 🔌 APIs & Integrations
  - Key interfaces between systems
  - External services

  ## 🗄️ Infrastructure & Storage
  - DB strategy, caching, file storage

  ## 🔒 Security & Scalability
  - Auth, rate limits, scaling approach

  ## ⚠ Risks & Open Questions
  - Technical & Product risks
  - Unknowns requiring validation

  ---
  # 📦 Deliverables & Milestones
  - **Milestone 1:** [Name] – [Description]
  - next milestone...
  ```

### 3. Milestone (Deliverable with Product Value)
- **What it is:** A checkpoint *within* a project that represents a shippable increment of product value (e.g., Inside the "Trigger Engine" project, Milestone 1 is "Webhooks", Milestone 2 is "Cron").
- **Linear Object:** `Project Milestone` (Use `save_milestone` MCP tool).
- **Description:** One-liner goal + key requirements. Lightweight by design — the real detail lives in Epics and Tickets underneath.

### 4. Epic (Technical Milestone)
- **What it is:** A grouping of technical tasks needed to achieve a milestone (e.g., "Build CRUD API for Workflows"). Epics can stretch across multiple milestones.
- **Linear Object:** `Parent Issue` (An issue that contains sub-issues).
- **Formatting Rules:** Concise bullet points. 3-5 key points per section. Shorthand where appropriate.
- **Description Requirements:** Must use the following Markdown template:

  ```markdown
  ## 🏗️ Architecture Context
  - Which chunk of the Project HLD this epic covers
  - Key technical decisions relevant to this epic

  ## 🔌 API Endpoints
  - `METHOD /route` — purpose, request/response contract
  - *(list all endpoints this epic introduces or modifies)*

  ## 🧱 Component Breakdown
  - Component/module name — what it does, file location
  - *(list all components this epic introduces)*

  ## 🔗 Dependencies
  - Other epics, external systems, or libraries this depends on

  ## 📋 Sub-Tickets Overview
  - Ticket title — one-liner description
  - *(list all child tickets)*
  ```

### 5. Ticket (Atomic Unit of Work)
- **What it is:** A single Pull Request. A specific API endpoint, a UI component, or a test suite.
- **Linear Object:** `Issue` (Use `save_issue` MCP tool).
- **Formatting Rules:** Concise bullet points. 3-5 key points per section. Shorthand where appropriate.
- **Description Requirements:** Must use the following Markdown template:

  ```markdown
  ## 🔧 Implementation Details
  - Exact technical steps
  - File paths, function signatures
  - Libraries / utilities to use

  ## 🧩 Data Models
  - Exact DB schemas, TypeScript interfaces, or Python Pydantic models
  - Field types, constraints, defaults

  ## ✅ Definition of Done (DoD)
  - Required tests (unit, integration, E2E)
  - Code review requirements
  - Documentation updates

  ## 🔬 Technical AC (Acceptance Criteria)
  - Functional requirements that must pass
  - Performance / latency constraints

  ## 🎨 Visual AC (UI tickets only)
  - Exact CSS variables, DOM hierarchy
  - Hover / active / error / empty states
  - Spacing, animations, transitions

  ## ⚠️ Edge Cases
  - Error handling
  - Empty states, boundary conditions
  - Concurrent access scenarios
  ```

## Operating Procedure
1. **Always plan top-down.** Start by defining the thematic Initiatives with full context.
2. **Break Initiatives into Projects.** Ensure every Project has a comprehensive Spec + ADR + HLD.
3. **Wait for approval.** Do not generate Issues/Tickets until the user explicitly approves the Project landscape.
4. **Create or Re-use the Skeleton Structure.** If a skeleton already exists, REUSE existing tickets instead of canceling and recreating. If starting from scratch, create Epics, Milestones, and Tickets with minimal placeholder details to establish the hierarchy.
5. **Split if Needed.** If a ticket is too large during research or implementation, split the atomic ticket into two.
