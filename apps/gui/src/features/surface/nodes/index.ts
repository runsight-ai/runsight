import { StartNode } from "./StartNode";
import { SoulNode } from "./SoulNode";

export const nodeTypes = {
  start: StartNode,
  soul: SoulNode,
} as const;

export { StartNode, SoulNode };
