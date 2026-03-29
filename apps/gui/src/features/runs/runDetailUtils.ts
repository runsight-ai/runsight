export function mapRunStatus(
  status: string,
): "idle" | "pending" | "running" | "completed" | "failed" | "paused" {
  switch (status) {
    case "completed":
    case "success":
      return "completed";
    case "failed":
    case "error":
      return "failed";
    case "running":
      return "running";
    case "pending":
    default:
      return "pending";
  }
}

export function getIconForBlockType(blockType: string): string {
  if (blockType.includes("agent") || blockType.includes("llm")) return "user";
  if (blockType.includes("condition") || blockType.includes("if")) return "layers";
  if (blockType.includes("input") || blockType.includes("output")) return "mail";
  return "server";
}
