---
title: Workspace Isolation
description: How Runsight isolates LLM block execution with per-run workspaces, mediated host capabilities, and Unix-local workers.
---

Runsight isolates LLM block execution around a **workspace** rather than around a provider or a container backend. The durable contract is:

1. The parser wraps LLM blocks with `IsolatedBlockWrapper`.
2. At execution time, the wrapper builds a `WorkspaceRunRequest`.
3. A workspace harness executes the request and validates a `ResultEnvelope`.
4. The wrapper converts the validated result back into normal `BlockOutput`.

The current local implementation of that contract is `UnixLocalHarness`. It creates a fresh workspace session, starts a local Unix worker process inside that session's runtime directory, mediates host capabilities through IPC, validates the worker result, and cleans up according to the workspace policy.

:::note
Workspace isolation is a credential, state, and workspace boundary. The current Unix-local backend is not a hard OS security sandbox: it does not add container namespaces, cgroups, or seccomp. It is the architecture layer that lets stricter backends be added later without changing workflow YAML, parser contracts, or block wrappers.
:::

## Deployment hardening

Workspace isolation and container hardening are separate layers. The workspace boundary governs each isolated block run; the Docker deployment also applies service-level process controls around Runsight itself.

- **Layer 1 — Container hardening:** Docker deployments run as a non-root/unprivileged user, drop Linux capabilities, prevent privilege escalation, and apply container CPU and memory limits.

## Why workspace isolation

LLM blocks accept arbitrary prompts and may request model calls, tools, HTTP access, or file operations. Runsight treats those requests as work that must cross an explicit boundary:

- Model provider keys stay in the host runtime.
- HTTP credentials and URL allowlists stay in host-only bindings.
- Executable tools stay registered on the host.
- Worker-visible state is serialized into a manifest and policy.
- File operations mediated by the host are scoped to the run workspace.

This design keeps the public execution model provider-neutral. The worker asks the host to perform model and tool work through the workspace IPC layer. The host decides which provider credentials, HTTP credentials, allowlists, and executable tool handlers apply to that run.

## The workspace boundary

When workflow YAML is parsed, LLM blocks are wrapped with `IsolatedBlockWrapper`. At execution time the wrapper sends a `WorkspaceRunRequest` to `UnixLocalHarness`.

The request contains serializable data the worker is allowed to know:

| Data | Purpose |
|------|---------|
| Block manifest | Describes the block, inputs, and runtime-visible configuration |
| Workspace manifest | Lists files to materialize into the run workspace |
| `WorkspacePolicy` | Runtime policy for the session |
| Worker tool metadata | Serializable declarations for tools the worker may request |

Host-only bindings are intentionally separate. `WorkspaceHostBindings` carries provider API keys, HTTP credentials, URL allowlists, and executable host tools. Those bindings are consumed by the harness to build host-side IPC handlers and are not serialized into the worker manifest or injected as worker environment secrets.

For HTTP tools, request-backed custom tools seed the allowlist from their host-side request URL. Dynamic built-in `http` calls use the host-only `RUNSIGHT_HTTP_URL_ALLOWLIST` setting, a comma- or whitespace-separated list of allowed hostnames or URLs. Empty allowlists deny mediated HTTP before any network request is made.

## Workspace materialization

`UnixLocalHarness` owns the local workspace base by default. For each session it creates a fresh child workspace and:

- Validates that manifest paths are relative.
- Materializes declared files under the harness-owned workspace root.
- Creates the runtime working directory.
- Starts the worker with `cwd` set to that runtime directory.
- Scopes host-mediated file reads and writes to the same canonical workspace root.
- Applies cleanup according to the workspace policy.

The important detail is that process `cwd` and mediated file I/O share one canonical root. A block can reason about its workspace consistently, while the host still validates mediated file paths against the session root.

## IPC and authentication

The worker discovers its IPC configuration from one environment variable:

```text
RUNSIGHT_IPC_CONFIG_B64=<base64-json IPCClientConfig>
```

That encoded `IPCClientConfig` is the current worker discovery contract. The worker uses it to connect to the host-side IPC handlers for model calls, tool execution, HTTP access, and file access.

Worker IPC handlers are for model calls, tool execution, HTTP access, and file access. Heartbeats are emitted as stderr JSON lines and monitored by the harness. The final `ResultEnvelope` is written to stdout as JSON and validated by the harness before the wrapper converts it back into `BlockOutput` for the normal workflow execution path.

## Policy and capabilities

`WorkspacePolicy` is runtime policy, not just documentation. It validates modes and controls the workspace session behavior the harness can enforce. The serializable request shape, including the worker manifest and policy data, is validated before execution.

`PolicyCapabilityReport.from_policy` reports capability entries conditionally from the policy:

| Capability area | Unix-local behavior |
|-----------------|---------------------|
| Raw network deny | Advisory in Unix-local when requested by policy |
| Raw filesystem deny | Advisory in Unix-local when requested by policy |
| Credential host binding | Enforced when credential host-binding policy applies |
| Mediated file constraints | Enforced when mediated file policy applies |
| Materialization size limits | Enforced when workspace materialization limits apply |

Because Unix-local workers are local Unix processes, direct process-level network and filesystem restrictions are advisory. Runsight's enforced controls apply to host-mediated capabilities: provider calls, credentialed HTTP calls, registered tool execution, materialized workspace files, and mediated file operations.

## Tool execution

Tool execution is split across two registries:

| Registry | Visibility | Contents |
|----------|------------|----------|
| `WorkerToolRegistry` | Worker-visible | Serializable tool names and metadata |
| `HostToolExecutionRegistry` | Host-only | Executable tool references and secrets |

A worker can request a tool only by using worker-visible metadata. The host executes the tool only when the same name exists in the host execution registry for that run. This keeps tool discovery serializable while keeping executable references and secrets out of the worker manifest.

## Provider-neutral model calls

The workspace harness does not depend on a specific model provider. The worker uses a proxied runner/client over IPC. The host-side handler resolves the provider from the requested model name and the API keys available in the run's host bindings.

Budget enforcement and tracing stay on the host side, so model calls made from isolated blocks still participate in normal Runsight accounting. See [Budget & Limits](/docs/execution/budget-and-limits) for budget configuration.

## Assertions

Assertions that use model calls for grading, such as `llm_judge`, use the same host-mediated model path. Their model calls are still budgeted and observed through the workspace boundary.

See [Custom Assertions](/docs/evaluation/custom-assertions#llm-graded-assertions-llm_judge) for assertion configuration details.

## Trade-offs

Workspace isolation gives Runsight a stable execution boundary without making the local backend pretend to be stronger than it is.

| Property | What Unix-local provides |
|----------|--------------------------|
| Fresh workspace | Each session gets a harness-owned workspace root and runtime working directory |
| Credential isolation | Provider keys, HTTP credentials, allowlists, and executable tools stay host-only |
| File mediation | Host-mediated reads and writes are scoped to the session root |
| Supervision | Worker heartbeat, timeout, result validation, and cleanup are owned by the harness |
| Backend portability | Parser, wrapper, request, and result contracts are backend-neutral |
| OS sandboxing | Not a container-grade boundary in the current local implementation |

Future backends can provide stronger OS-level enforcement behind the same `WorkspaceRunRequest` to `ResultEnvelope` contract. The current docs describe the shipped Unix-local runtime only.

<!-- Linear: RUN-999, RUN-1000, RUN-1001, RUN-1002, RUN-1003, RUN-1004, RUN-1005, RUN-1006, RUN-1007 - last verified against codebase 2026-05-09 -->
