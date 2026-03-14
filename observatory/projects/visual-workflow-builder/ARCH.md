# Technical Architecture: Visual Workflow Builder

## React Component Tree
- `WorkflowCanvas`: The main container wrapping `ReactFlowProvider`. Handles global state syncing and layout.
  - `CanvasSidebar`: The palette of available nodes (Agents, Flow Control, etc.).
  - `ReactFlow`: The core graph renderer.
    - `CanvasNode`: Custom node component. Displays status badges, execution costs, and node types.
  - `InspectorPanel`: Sidebar that appears when a node is selected. Uses Schema UI to render dynamic forms based on node type.
  - `BottomPanel`: Execution logs and summary.

## Zustand Store Schema
```typescript
interface CanvasState {
  nodes: Node<StepNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;
  viewMode: "visual" | "code";
  
  // Actions
  setNodes: (nodes: Node<StepNodeData>[]) => void;
  setEdges: (edges: Edge[]) => void;
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  selectNode: (id: string | null) => void;
  setViewMode: (mode: "visual" | "code") => void;
}
```

## Node UI Schema Format
To keep the frontend decoupled from backend primitive definitions, the backend provides a JSON Schema for each node type. The frontend parses this to render inputs.
```json
{
  "type": "object",
  "properties": {
    "system_prompt": {
      "type": "string",
      "ui:widget": "textarea",
      "title": "System Prompt"
    },
    "temperature": {
      "type": "number",
      "default": 0.7,
      "minimum": 0,
      "maximum": 2
    }
  }
}
```

## ComfyUI-Style Reference-First Payload
Instead of a deeply nested tree, the workflow compiles into a flat dictionary where nodes reference each other by ID. This ensures easy serialization and backend execution (matching ComfyUI's architecture).
```json
{
  "node_1": {
    "class_type": "LinearAgent",
    "inputs": {
      "system_prompt": "You are a helpful assistant",
      "input_text": ["node_0", 0] // Reference to output 0 of node_0
    }
  },
  "node_2": {
    "class_type": "FileWriter",
    "inputs": {
      "file_path": "output.txt",
      "content": ["node_1", 0]
    }
  }
}
```
