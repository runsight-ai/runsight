# Product Specification: Visual Workflow Builder

## 📖 Overview & Context
We need a robust, drag-and-drop Visual Workflow Builder to empower users to construct complex AI agent workflows effortlessly. This tool replaces manual YAML editing with an intuitive interface, inspired by ComfyUI and Langflow, allowing for seamless edge connection, node configuration, and payload execution.

## 🎯 Goals & Expected Outcomes
- Provide a full visual representation of agentic workflows.
- Allow users to drag and drop nodes (Agents, Steps) and connect them.
- Achieve feature parity with the YAML editor but with a superior UX.

## 🚧 Scope
- **In Scope:** Drag-and-drop canvas, customizable nodes, edge connecting, node inspector, Zustand-based state management, schema-driven UI forms for node configuration.
- **Out of Scope:** Multi-player real-time collaboration.

## 🔄 User Flow & Experience
1. User opens a workflow and sees the Canvas view.
2. User drags a new step from the Sidebar onto the Canvas.
3. User connects the output of one node to the input of another.
4. User clicks a node to open the Inspector and configures inputs based on auto-generated schema.

## 📦 Deliverables & Milestones

### Milestone 1: Core Canvas & Schema UI
- **Description:** Implement the base ReactFlow canvas, node rendering, and schema-driven inspector.
- **Requirements:**
  - Render `@xyflow/react` canvas with `CanvasNode` components.
  - Implement drag-and-drop from `CanvasSidebar`.
  - Create the Zustand store for nodes and selection.
  - Build `InspectorPanel` that renders dynamic forms based on the Node UI Schema.

### Milestone 2: Edges & Payload Compilation
- **Description:** Enable node connections and compile the visual graph into a flat JSON payload.
- **Requirements:**
  - Implement edge connection logic with validation (matching types).
  - Implement payload compiler that traverses the ReactFlow graph and outputs a ComfyUI-style reference-first flat JSON structure.
  - Sync flat JSON graph with the backend execution engine.

### Milestone 3: Canvas Polish & Minimap
- **Description:** Add UX improvements, minimap, zoom controls, and execution state visualization.
- **Requirements:**
  - Add ReactFlow `MiniMap` and `Controls`.
  - Implement execution state animations (e.g., pulsing borders for running nodes).
  - Add "Auto-Layout" functionality for messy graphs.
