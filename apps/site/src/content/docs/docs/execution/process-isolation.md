---
title: Process Isolation
description: How Runsight isolates LLM block execution in subprocesses — trust boundaries, credential proxying, budget enforcement, and the layered defense model.
---

Runsight executes every LLM block in a separate subprocess. The subprocess has no API keys, no access to engine memory, and no credentials. Every interaction with the outside world — LLM calls, tool invocations, HTTP requests, file writes — is mediated through a supervised IPC channel where the engine enforces budget limits, records traces, and validates every request.

## Why process isolation

LLM blocks accept arbitrary prompts and execute tool calls determined by model output. A compromised or misbehaving model could attempt to:

- Read API keys from environment variables and exfiltrate them
- Mutate engine state shared across blocks
- Bypass budget enforcement by calling the LLM provider directly
- Access credentials for unrelated services

Process isolation eliminates these risks by creating a **credential boundary**: API keys never enter the subprocess. Every LLM call is proxied through the engine, which holds the real keys, enforces budgets, and records observability data.

:::note
Process isolation is a **credential and state boundary**, not a full OS-level sandbox. See [Known Limitations](#known-limitations) for what is and is not protected.
:::

## The trust boundary

The isolation architecture splits execution into two processes with a strict boundary between them.

![Trust boundary between engine and subprocess](/diagrams/trust-boundary.svg)

The subprocess receives only four environment variables: `PATH`, the IPC socket path, a single-use authentication token, and a macOS library path. API keys, cloud credentials, `HOME`, `USER`, and all other environment variables are never passed.

## How communication works

The engine and subprocess communicate over four purpose-built channels.

![Four communication channels between engine and subprocess](/diagrams/communication-channels.svg)

- **stdin** delivers the block configuration once at startup — what to execute, which soul, what state.
- **stdout** carries the final result once on exit — output text, cost, tokens, exit handle.
- **stderr** streams heartbeat messages every 5 seconds for liveness monitoring and stall detection.
- **Unix socket** is the bidirectional IPC channel for all engine interactions — LLM calls, tool execution, HTTP requests, and file operations.

## Authentication

Each subprocess gets a **single-use grant token** — a random string minted by the engine just before the subprocess is spawned:

- The token must be presented on the first IPC message
- After acceptance, the token is consumed — a second connection attempt is rejected
- The token expires after 120 seconds if the subprocess is too slow to connect
- The subprocess clears the token from its own environment immediately after connecting

This ties authentication to the subprocess lifecycle: the token works exactly once, for exactly one process, within a bounded time window.

## Proxied LLM calls

The subprocess does not call LLM providers directly. It uses a proxied client with the same interface as the real LLM client — block code calls the same method, but the call is routed through the IPC channel to the engine.

![LLM call proxied through engine](/diagrams/llm-proxy-flow.svg)

The engine resolves the correct API key for the requested model, makes the actual API call, and returns the result. A strict allowlist controls which generation parameters the subprocess can set — standard parameters like `max_tokens` and `temperature` are allowed, while parameters that could redirect the API call are silently dropped.

## The interceptor chain

Every request crossing the IPC boundary passes through a chain of interceptors — engine-side middleware that validates, meters, and traces each request without changing the protocol.

![Interceptor chain request and response flow](/diagrams/interceptor-chain.svg)

Interceptors run in **forward order** on the request path and **reverse order** on the response path — an "onion" pattern where each interceptor sets up context on the way in and cleans up on the way out.

Adding a new engine concern — governance, rate limiting, audit logging — means writing one interceptor and registering it. No protocol changes, no handler modifications, no subprocess updates. The architecture is designed so that new engine capabilities compose without touching existing code.

## Budget enforcement

Budget limits defined in workflow YAML work transparently across the isolation boundary:

- **Before each LLM call:** The budget interceptor checks the remaining budget. If exceeded, the call is rejected before the LLM provider is contacted — no money spent.
- **After each LLM call:** The interceptor accrues the reported cost and tokens. Costs propagate up the parent chain — block-level costs roll up to the workflow budget.
- **When budget is exceeded mid-execution:** The current call's result is returned (the money is already spent). The next call is rejected. This avoids discarding work you've already paid for.

See [Budget & Limits](/docs/execution/budget-and-limits) for the full YAML configuration.

## Smart assertions

Assertions that use LLM calls for grading (like `llm_judge`) run through the same isolation path. The judge's LLM call goes through the IPC channel, passes through the interceptor chain, and its cost counts toward the block's budget. Simple custom assertions (Python plugins that return pass/fail) continue to run in a minimal subprocess without IPC access.

See [Custom Assertions](/docs/evaluation/custom-assertions#llm-graded-assertions-llm_judge) for configuration details.

## Layered defense model

Runsight uses defense-in-depth with four active layers.

![Layered defense model](/diagrams/layered-defense.svg)

- **Layer 1 — Container hardening:** The Docker deployment runs as an unprivileged user, drops all Linux capabilities, prevents privilege escalation, and enforces memory and CPU limits. A runaway process is killed by the kernel, not the host.
- **Layer 2 — Process isolation:** The subprocess runs in a separate OS process. No shared memory, no API keys, no credentials.
- **Layer 3 — IPC mediation:** Every engine interaction passes through the interceptor chain. Budgets enforced per call. Actions validated against an allowlist. Traces recorded automatically.
- **Layer 4 — Nested subprocess:** Code execution (CodeBlock) and simple assertion plugins run in a further-nested subprocess with an even more restricted environment.

## Known limitations

Process isolation is a credential boundary, not a full execution sandbox.

| What | Status | Detail |
|------|--------|--------|
| API key isolation | **Protected** | Keys never enter subprocess environment or memory |
| Engine state isolation | **Protected** | No access to engine memory or database |
| Budget enforcement | **Protected** | Every LLM call passes through the budget interceptor |
| Observability | **Protected** | Every IPC action creates a trace span |
| Network access | Not restricted | Subprocess can use Python `socket` directly (but has nothing to exfiltrate) |
| Filesystem access | Partially restricted | IPC file handler is sandboxed; direct `open()` calls are not |
| CPU / memory limits | **Container-level** | mem_limit, memswap_limit, and cpus enforced via Docker cgroups |
| Python imports | Not restricted | Subprocess can import any installed package |

The isolation boundary works because the subprocess has **nothing valuable** — no API keys, no credentials, no engine state. Even if the subprocess makes direct network calls, it has nothing sensitive to send.

<!-- Linear: RUN-391 — last verified against codebase 2026-04-11 -->
