import { StartNode } from "./StartNode";
import { SoulNode } from "./SoulNode";
import { TaskNode } from "./TaskNode";

export const nodeTypes = {
  start: StartNode,
  soul: SoulNode,
  task: TaskNode,
} as const;

export { StartNode, SoulNode, TaskNode };
