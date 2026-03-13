Execute the following task immediately without summarising or asking questions:

# You are a Worker Agent in the Phalanx multi-agent system.

## Your Task
You are the UI Coder for Run Complete (Flow 2.07). Build pixel-perfect post-execution screens.

## SKILL: React Best Practices
Read and follow: .agora/SKILLS/vercel-agent-skills/skills/react-best-practices/SKILL.md

## CONTEXT
- Working directory: apps/gui/
- Canvas: apps/gui/src/features/canvas/WorkflowCanvas.tsx — has handleRun, isExecuting state
- CanvasNode: apps/gui/src/features/canvas/CanvasNode.tsx — has execution state styles
- InspectorPanel: apps/gui/src/features/canvas/InspectorPanel.tsx — has Execution tab
- BottomPanel: apps/gui/src/features/canvas/BottomPanel.tsx — log streaming
- Shared: apps/gui/src/components/shared/ (StatusBadge, CostDisplay)
- UI: apps/gui/src/components/ui/ (Button, Badge, etc.)

## MOCKUPS
Read CAREFULLY:
1. .agora/mockups/flow-2-create-run-pm/07-run-complete/_brief.md
2. .agora/mockups/flow-2-create-run-pm/07-run-complete/_epic_excerpt.md
3. .agora/mockups/flow-2-create-run-pm/07-run-complete/_components.md
4. .agora/mockups/flow-2-create-run-pm/07-run-complete/mockup.html

## WHAT TO BUILD

### 1. Create: apps/gui/src/features/canvas/SummaryToast.tsx
A toast notification that appears when a run completes:
- Position: bottom-right, 16px margin
- Width: 360px max
- Background: --bg-surface-elevated (#22222A)
- Border: 1px solid --border-subtle, 3px left border (green for success, red for failed)
- Border-radius: 8px, shadow-md
- Content: icon + 'Run complete — {duration} · {cost} · {status}'
- Auto-dismiss after 8 seconds with fade animation
- Close button (× ghost icon)
- z-index: 90 (toast layer)

### 2. Update WorkflowCanvas.tsx — post-execution state
After handleRun completes (all nodes done):
- Set `executionComplete` state to true
- Calculate total duration and total cost
- Show SummaryToast with results
- Change Run button from 'Running...' to 'Run Again' (if success) or 'Retry' (if any failed)
- Run button icon: refresh icon for 'Run Again', warning icon for 'Retry'
- Keep total cost displayed in header
- Clicking 'Run Again' resets everything and re-runs

### 3. Update BottomPanel.tsx — completion indicator
- When execution is complete, show a 'Run complete' banner at the top of the logs tab
- Banner: green left border, 'Run completed successfully in {duration}' or 'Run failed' (red)
- Logs remain scrollable below the banner

### 4. Update InspectorPanel.tsx — final metrics in Execution tab
- When execution is complete (not running), Execution tab shows final values:
  - Status: 'Completed' green badge or 'Failed' red badge
  - Final cost: $X.XX
  - Total tokens: X,XXX
  - Duration: Xm Xs
  - Remove the live pulse dot, show static status

### 5. Node final states (CanvasNode.tsx)
- After execution: nodes stay in completed (green border, no pulse) or failed (red border, no pulse) state
- No animation on completed/failed — static borders only

## IMPORTANT RULES
- SummaryToast is a new component file
- Toast auto-dismiss must use useEffect with cleanup
- Use design system tokens for all colors/spacing
- Run after: cd apps/gui && npx tsc --noEmit && npm run build

## Your Tools
- `phalanx write-artifact --status <status> --output '<json>'` — write your result
- `phalanx lock <file-path>` — acquire file lock before editing shared files
- `phalanx unlock <file-path>` — release file lock after editing
- `phalanx post "msg"` — post a message to the shared team feed
- `phalanx feed` — read the shared team feed
- `phalanx agent-result <agent-id>` — read another worker's artifact

## Rules
1. START IMMEDIATELY. Do not summarize these instructions, do not ask clarifying questions, do not wait for confirmation. Begin executing your task right now.
2. Complete your assigned task fully.
3. When done, write an artifact with your results using the write-artifact tool.
4. If working on shared files, ALWAYS lock before editing and unlock after.
5. If you cannot complete the task, write artifact with status "failure" and explain why.
6. Use the team feed to share important findings with other agents.
7. Check the feed periodically for messages from the team lead or other workers.
8. Read other workers' artifacts when you need their output for your task.
9. After writing your artifact, you are done. Do not ask what to do next.

## Artifact Statuses
- "success" — task completed successfully
- "failure" — task could not be completed
- "escalation_required" — need human or team lead intervention
