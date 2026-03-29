import { useParams } from "react-router";
import { CanvasTopbar } from "./CanvasTopbar";

export function Component() {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="flex flex-col h-full">
      <CanvasTopbar workflowId={id!} />
      <div className="flex-1" />
    </div>
  );
}
