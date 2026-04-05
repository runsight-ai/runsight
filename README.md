# Runsight

**The ultimate mission control for AI agents.**

*Build like Terraform. Orchestrate like Kubernetes. Monitor like Grafana.*

---

## 🛑 The Problem: We built the workers, but forgot the factory.

By 2026, building an AI agent is easy. Running a *team* of them in production is a nightmare. 

- **Silent Failures:** 67% of agent failures are found by users, not monitoring. Agents get stuck in infinite loops or hallucinate without throwing errors.
- **Cost Overruns:** 96% of teams report unexpected LLM charges. A single rogue agent can burn hundreds of dollars in minutes.
- **Zero Control:** Once you hit "run" on a LangChain or CrewAI script, it's a black box. You can't pause it, you can't fix a bad prompt mid-flight, and you can't intervene.

## 🚀 The Solution: Runsight

Runsight is a meta-framework and visual observability platform designed specifically for multi-agent workflows. It gives you the runtime controls you need to put agents into production safely.

### Core Features

- 📊 **Live DAG Visualization:** Watch your agents think, reason, and act in real-time. See exactly which node is running, pending, or failed.
- ⏸️ **Runtime Intervention:** The only platform that lets you **pause, kill, or message** a running agent mid-execution directly from a visual UI.
- 💸 **Real-Time Cost Tracking:** Watch the cost tick up live. Track token spend per node, per workflow, and per day. Set hard budgets that kill rogue agents automatically.
- 📝 **Declarative Workflows:** Define your agent teams, tasks, and state machines as version-controlled YAML files on disk. 
- 🛠️ **Mid-Flight Prompt Editing:** Agent stuck? Pause the node, edit the prompt in the inspector, and hit retry—without restarting the whole workflow.

## 🏗️ Architecture: The Three Layers

Runsight is built on three distinct layers:

1. **The Builder (Terraform):** Define workflows, souls (agent identities), and tasks using simple YAML files.
2. **The Runtime (Kubernetes):** A deterministic execution engine that handles state, retries, dispatch branches, and multi-agent collaboration patterns.
3. **Mission Control (Grafana):** A React/Next.js frontend that connects to the runtime via SSE (Server-Sent Events) to stream logs, status, and costs live.

## 🏁 Quick Start

*(Coming soon: Installation instructions for the core engine and UI)*

```bash
# Clone the repository
git clone https://github.com/runsight-ai/runsight.git
cd runsight

# Install dependencies (requires Python 3.10+)
pip install -e .

# Start the Mission Control UI
runsight ui start
```

## Code Indexing With Codebones

Runsight contributors use `codebones` for local code search and structural lookups.
Use the `uv` tool install flow so each checkout picks up the fixed indexer behavior:

```bash
uv tool install codebones
# or, if you already have it installed
uv tool upgrade codebones
```

Verify the CLI that your current checkout will use before relying on the local index:

```bash
uv tool list
codebones --version
```

Indexes are local cache artifacts, not shared repo state. Rebuild or reindex from the
root of the checkout, clone, or worktree you are actively using:

```bash
codebones index .
```

Run `codebones index .` again after pulling large changes, switching branches, or
deleting or moving files. Reindexing should rebuild search results so removed files no
longer appear in named searches or in `codebones search ""`.

The cache lives in a local `codebones.db` file for that checkout/worktree/clone. If an
older cache breaks after an upgrade or starts returning stale data, delete the cache and
rebuild it in place:

```bash
rm -f codebones.db
codebones index .
```

If you keep multiple worktrees open, repeat that reset in each one separately because
each checkout has its own `codebones.db`.

## 📄 License & Open Core

Runsight operates on an **Open-Core** model. 
- The core orchestration engine and basic UI are open-source under the **MIT License**.
- Advanced fleet management, RBAC, and enterprise integrations will be available under a commercial license.

---
*Runsight: Because your agents shouldn't be running blind.*
