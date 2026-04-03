import { WorkflowSurface, type WorkflowSurfaceLayoutProps } from "./WorkflowSurface";

type ForkDraftWorkflowSurfaceProps = Omit<WorkflowSurfaceLayoutProps, "initialMode">;

export function ForkDraftWorkflowSurface(props: ForkDraftWorkflowSurfaceProps) {
  return <WorkflowSurface {...props} initialMode="fork-draft" />;
}

export const Component = ForkDraftWorkflowSurface;

export default ForkDraftWorkflowSurface;
