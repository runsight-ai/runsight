import { WorkflowSurface, type WorkflowSurfaceLayoutProps } from "./WorkflowSurface";

type WorkflowEditorSurfaceProps = Omit<WorkflowSurfaceLayoutProps, "initialMode">;

export function WorkflowEditorSurface({
  workflowId,
  ...props
}: WorkflowEditorSurfaceProps) {
  return <WorkflowSurface {...props} workflowId={workflowId} initialMode="workflow" />;
}

export const Component = WorkflowEditorSurface;

export default WorkflowEditorSurface;
