# Architectural Report: Open-Source Visual Node Editors

This report synthesizes the architectural approaches of industry-leading open-source node-based canvases (`langflow`, `Flowise`, `dify`, `n8n`, `ComfyUI`), extracting core patterns to define the optimal MVP strategy for Runsight's Visual Workflow Builder.

## 1. Canvas Library Implementations
* **React Flow Dominance**: `langflow`, `Flowise`, and `dify` all utilize **React Flow**. It has become the de-facto standard for React-based applications due to its customizability, robust edge routing, and minimap/controls ecosystem.
* **Custom / Legacy Implementations**: 
  * `n8n` relies on a custom Vue-based DOM/SVG canvas rendering engine tightly coupled with their domain structure.
  * `ComfyUI` uses `LiteGraph.js`, a vanilla JS engine optimized for heavy, high-performance graph processing common in the generative AI ecosystem.

## 2. State Management
* **Zustand**: `langflow` and `dify` use `Zustand` for lightweight, flux-like state management. This pairs exceptionally well with React Flow's internal state.
* **Redux Toolkit**: `Flowise` uses `Redux` and `@reduxjs/toolkit` for strictly enforced unidirectional data flow.
* **Pinia / Vanilla**: `n8n` utilizes `Pinia` (standard for modern Vue apps), while `ComfyUI` relies on `LiteGraph`'s internal JS memory structures.

## 3. Visual Graph to Execution Payload Translation
There are two primary paradigms for translating visual graphs into runnable backend payloads:
* **Topology-First (The Langflow / Dify approach)**:
  The frontend sends a generic Graph AST consisting of `Vertices` (nodes) and `Edges` (connections). The backend iterates over the DAG, handling the variable passing dynamically during execution (e.g., matching edge connections to explicit Variable Pools or template bindings like `{{#node_id.output#}}`).
* **Prompt/Reference-First (The ComfyUI approach)**: 
  The frontend graph is flattened into a single JSON dictionary where keys are `node_id`s, and values specify the `class_type` and its explicit `inputs`. Graph edges aren't sent as separate entities; instead, an input value is just a tuple reference to another node's output: `[parent_node_id, output_index]`. This produces an incredibly efficient execution queue with deep caching capabilities.
* **Item-Loop DAG (The n8n approach)**:
  Execution operates on pure JSON structures (`INodeExecutionData[][]`). Data is passed chronologically through nodes, handling mapping and batch-looping intrinsically based on an execution context.

## 4. Custom Node Definitions
All leading platforms have completely divorced node logic from custom frontend components to enable massive scalability.
* **Backend-First, Schema-Driven UI (ComfyUI / Langflow)**: Nodes are written purely in Python classes. The class explicitly defines its schema (e.g., ComfyUI's `INPUT_TYPES()` classmethod or Langflow's Pydantic field generation). The frontend receives this generic JSON schema and renders standard input fields (dropdowns, text areas, toggles) dynamically. 
* **TypeScript-First, Interface-Driven (n8n / Flowise)**: Nodes are TypeScript classes implementing a strict `INode` or `INodeType` interface. The `description.properties` arrays act as the JSON schema definition for the frontend UI. 

---

## Strategic Recommendation for Runsight MVP

To build a scalable, highly maintainable Visual Workflow Builder for Runsight, we should adapt the following **"Best Practice" stack**:

### 1. Canvas & State
* **Library**: `React Flow`
* **State Manager**: `Zustand`
* **Why**: The combination of React Flow and Zustand is the industry golden standard for React environments. It allows rapid iteration and handles large graphs effortlessly without the boilerplate of Redux or the custom maintenance burden of n8n.

### 2. Execution Payload Format (The ComfyUI Method)
* Steal the **ComfyUI Reference-First JSON structure**. 
* **Why**: Explicit edge arrays are harder to serialize/deserialize safely and validate. A flat dictionary of `NodeID -> { type, inputs: { arg1: "static_value", arg2: ["parent_node_id", 0] }}` is trivially parsed into a DAG by the backend. It inherently maps to functional execution, making distributed worker delegation and graph validation extremely fast.

### 3. Node Definitions (Schema-Driven UI)
* Adopt a **Backend-First Schema-Driven** architecture.
* **Why**: NEVER write custom React components for individual nodes. Define node logic entirely in Python/TypeScript backend classes. These classes must expose a static schema property. The React Flow nodes should be entirely generic ("Dumb Nodes"), instantly rendering dynamic fields (inputs, toggles, connection handles) by parsing the backend schema at runtime. This allows AI agents to rapidly generate new integrations simply by writing backend logic, with zero frontend UI compilation required.
