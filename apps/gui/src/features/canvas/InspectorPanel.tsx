import { useState, useCallback, useMemo, useEffect } from "react";
import type { Node } from "@xyflow/react";
import type { StepNodeData, StepType } from "@/types/schemas/canvas";
import type { LogEntry } from "./BottomPanel";
import { useSouls } from "@/queries/souls";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  X,
  Plus,
  Sparkles,
  ChevronDown,
  Pause,
  Square,
  RotateCcw,
  Send,
  AlertCircle,
  Loader2,
  Check,
  X as XIcon,
  Play,
  ArrowLeft,
  Code2,
  FileJson,
  Terminal,
  History,
  GitBranch,
} from "lucide-react";
import { cn } from "@/utils/helpers";
import Editor from "@monaco-editor/react";

type TabId = "overview" | "prompt" | "conditions" | "execution" | "audit" | "versions";
type ConditionMode = "simple" | "expression" | "python";
type ConditionOperator = "contains" | "equals" | "starts_with" | "ends_with" | "greater_than" | "less_than" | "exists";
type ConditionType = "output_contains" | "status_equals" | "cost_exceeds" | "duration_exceeds" | "artifact_exists" | "always";

interface SimpleCondition {
  id: string;
  type: ConditionType;
  operator: ConditionOperator;
  value: string;
  thenStep: string;
  elseStep: string;
}

interface IncomingCondition {
  id: string;
  fromNode: string;
  type: "sequential" | "conditional";
  condition?: string;
}

interface ExpressionValidation {
  isValid: boolean;
  message?: string;
}

interface InspectorPanelProps {
  selectedNode: Node<StepNodeData> | null;
  onClose: () => void;
  onNodeUpdate: (nodeId: string, data: Partial<StepNodeData>) => void;
  isExecuting?: boolean;
  executionComplete?: boolean;
  elapsedTime?: number;
  finalDuration?: number;
  executionLogs?: LogEntry[];
  onPause?: () => void;
  onKill?: () => void;
  onRestart?: () => void;
  // Workflow nodes for step selection
  workflowNodes?: Array<{ id: string; name: string }>;
  // Incoming conditions for this node
  incomingConditions?: IncomingCondition[];
}

const STEP_TYPE_LABELS: Record<StepType, string> = {
  linear: "Linear",
  fanout: "Fan Out",
  debate: "Debate",
  message_bus: "Message Bus",
  router: "Router",
  gate: "Gate",
  synthesize: "Synthesize",
  workflow: "Workflow",
  retry: "Retry",
  team_lead: "Team Lead",
  engineering_manager: "Eng. Manager",
  placeholder: "Placeholder",
  file_writer: "File Writer",
};

const statusToVariant: Record<
  string,
  { variant: "pending" | "running" | "success" | "error" | "warning"; label: string }
> = {
  idle: { variant: "pending", label: "Idle" },
  running: { variant: "running", label: "Running" },
  completed: { variant: "success", label: "Completed" },
  failed: { variant: "error", label: "Failed" },
  paused: { variant: "warning", label: "Paused" },
};

const defaultStatusInfo = { variant: "pending" as const, label: "Idle" };

const CONDITION_TYPES: { value: ConditionType; label: string }[] = [
  { value: "output_contains", label: "output contains" },
  { value: "status_equals", label: "status equals" },
  { value: "cost_exceeds", label: "cost exceeds" },
  { value: "duration_exceeds", label: "duration exceeds" },
  { value: "artifact_exists", label: "artifact exists" },
  { value: "always", label: "always" },
];

const OPERATORS: { value: ConditionOperator; label: string }[] = [
  { value: "contains", label: "contains" },
  { value: "equals", label: "equals" },
  { value: "starts_with", label: "starts with" },
  { value: "ends_with", label: "ends with" },
  { value: "greater_than", label: ">" },
  { value: "less_than", label: "<" },
  { value: "exists", label: "exists" },
];

const AVAILABLE_VARIABLES = [
  "outputs.analyze-code.quality_report",
  "outputs.analyze-code.score",
  "outputs.analyze-code.suggestions",
  "outputs.security-check.risk_level",
  "outputs.security-check.security_issues",
  "artifacts.pr_data",
  "artifacts.code_diff",
  "workflow.name",
  "workflow.id",
  "step.status",
  "step.duration",
  "step.cost",
];

const PYTHON_STUB = `# Access workflow state via the workflow_state dict
# Available keys: outputs, artifacts, step, workflow

# Example: Check if code quality score is acceptable
score = workflow_state.get("outputs", {}).get("analyze-code", {}).get("score", 0)
risk_level = workflow_state.get("outputs", {}).get("security-check", {}).get("risk_level", "unknown")

# Return True to take the "Then" branch, False for "Else"
return score >= 7 and risk_level != "high"`;

export function InspectorPanel({
  selectedNode,
  onClose,
  onNodeUpdate,
  isExecuting = false,
  executionComplete = false,
  elapsedTime = 0,
  finalDuration = 0,
  executionLogs = [],
  onPause,
  onKill,
  onRestart,
  workflowNodes = [],
  incomingConditions = [],
}: InspectorPanelProps) {
  const { data: soulsData } = useSouls();
  const souls = soulsData?.items ?? [];

  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [conditionMode, setConditionMode] = useState<ConditionMode>("simple");
  const [messageText, setMessageText] = useState("");

  // Local state for inline editing
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState("");
  useEffect(() => {
    if (!editingName && selectedNode) {
      const d = selectedNode.data as StepNodeData;
      setNameValue(d?.name ?? "");
    }
  }, [selectedNode?.id, editingName, selectedNode]);

  // Simple mode state
  const [simpleConditions, setSimpleConditions] = useState<SimpleCondition[]>([
    {
      id: "1",
      type: "output_contains",
      operator: "contains",
      value: "",
      thenStep: "next",
      elseStep: "end",
    },
  ]);

  // Expression mode state
  const [expressionValue, setExpressionValue] = useState(
    "{{ outputs.analyze-code.score }} >= 7 and {{ outputs.security-check.risk_level }} != 'high'"
  );
  const [expressionValidation, setExpressionValidation] = useState<ExpressionValidation>({ isValid: true });
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [cursorPosition, setCursorPosition] = useState(0);

  // Python mode state
  const [pythonCode, setPythonCode] = useState(PYTHON_STUB);
  const [pythonTestResult, setPythonTestResult] = useState<{ success: boolean; result?: boolean; error?: string } | null>(null);
  const [isTestingPython, setIsTestingPython] = useState(false);

  const handleNameSubmit = useCallback(() => {
    if (selectedNode && nameValue.trim()) {
      onNodeUpdate(selectedNode.id, { name: nameValue.trim() });
    }
    setEditingName(false);
  }, [selectedNode, nameValue, onNodeUpdate]);

  const handleNameKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        handleNameSubmit();
      } else if (e.key === "Escape") {
        const d = selectedNode?.data as StepNodeData | undefined;
        setNameValue(d?.name ?? "");
        setEditingName(false);
      }
    },
    [handleNameSubmit, selectedNode]
  );

  const startEditingName = useCallback(() => {
    const d = selectedNode?.data as StepNodeData | undefined;
    setNameValue(d?.name ?? "");
    setEditingName(true);
  }, [selectedNode]);

  // Expression validation
  const validateExpression = useCallback((expr: string): ExpressionValidation => {
    if (!expr.trim()) {
      return { isValid: false, message: "Expression cannot be empty" };
    }

    // Check for valid Jinja2-like syntax
    const variableRegex = /\{\{\s*([\w\-.\[\]]+)\s*\}\}/g;
    const hasValidVariables = variableRegex.test(expr);

    if (!hasValidVariables && !expr.includes("==") && !expr.includes("!=") && !expr.includes(">") && !expr.includes("<")) {
      return { isValid: false, message: "Expression should contain variables or comparison operators" };
    }

    // Check for balanced brackets
    const openCount = (expr.match(/\{\{/g) || []).length;
    const closeCount = (expr.match(/\}\}/g) || []).length;
    if (openCount !== closeCount) {
      return { isValid: false, message: "Unbalanced brackets" };
    }

    return { isValid: true };
  }, []);

  const handleExpressionChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setExpressionValue(value);
    setExpressionValidation(validateExpression(value));
    setCursorPosition(e.target.selectionStart);
  }, [validateExpression]);

  const insertVariable = useCallback((variable: string) => {
    const beforeCursor = expressionValue.slice(0, cursorPosition);
    const afterCursor = expressionValue.slice(cursorPosition);
    const newValue = beforeCursor + `{{ ${variable} }}` + afterCursor;
    setExpressionValue(newValue);
    setExpressionValidation(validateExpression(newValue));
    setShowAutocomplete(false);
  }, [expressionValue, cursorPosition, validateExpression]);

  const testPythonCondition = useCallback(async () => {
    setIsTestingPython(true);
    // Simulate API call for testing Python condition
    await new Promise((resolve) => setTimeout(resolve, 1000));

    // Mock result - in real implementation this would call the backend
    const mockResult = Math.random() > 0.3;
    setPythonTestResult({
      success: true,
      result: mockResult,
    });
    setIsTestingPython(false);
  }, []);

  const addSimpleCondition = useCallback(() => {
    setSimpleConditions((prev) => [
      ...prev,
      {
        id: Math.random().toString(36).substr(2, 9),
        type: "output_contains",
        operator: "contains",
        value: "",
        thenStep: "next",
        elseStep: "end",
      },
    ]);
  }, []);

  const updateSimpleCondition = useCallback((id: string, field: keyof SimpleCondition, value: string) => {
    setSimpleConditions((prev) =>
      prev.map((cond) => (cond.id === id ? { ...cond, [field]: value } : cond))
    );
  }, []);

  const removeSimpleCondition = useCallback((id: string) => {
    setSimpleConditions((prev) => prev.filter((cond) => cond.id !== id));
  }, []);

  const availableSteps = useMemo(() => {
    const defaultSteps = [
      { value: "next", label: "Next step" },
      { value: "end", label: "End workflow" },
    ];
    const nodeSteps = workflowNodes.map((node) => ({
      value: node.id,
      label: node.name,
    }));
    return [...defaultSteps, ...nodeSteps];
  }, [workflowNodes]);

  if (!selectedNode) return null;

  const nodeData = selectedNode.data as StepNodeData;
  const stepType = nodeData.stepType ?? "linear";
  const displayName = nodeData.name ?? "Untitled";
  const status = nodeData.status ?? "idle";
  const statusInfo = statusToVariant[status] ?? defaultStatusInfo;

  // Show Execution tab if executing or node has execution data
  const showExecutionTab = isExecuting ||
    status === "running" ||
    status === "completed" ||
    status === "failed" ||
    status === "pending";

  const tabs: { id: TabId; label: string; icon?: React.ComponentType<{ className?: string }> }[] = [
    { id: "overview", label: "Overview" },
    { id: "prompt", label: "Prompt" },
    { id: "conditions", label: "Conditions" },
    ...(showExecutionTab ? [{ id: "execution" as TabId, label: "Execution" }] : []),
    { id: "audit", label: "Audit", icon: History },
    { id: "versions", label: "Versions", icon: GitBranch },
  ];

  return (
    <aside
      className="w-[320px] min-w-[280px] max-w-[480px] bg-[#16161C] border-l border-[#2D2D35] flex flex-col z-50 animate-in slide-in-from-right duration-200"
      aria-label="Node inspector panel"
    >
      {/* Header */}
      <div className="h-12 px-3 border-b border-[#2D2D35] flex items-center justify-between shrink-0">
        {editingName ? (
          <Input
            value={nameValue}
            onChange={(e) => setNameValue(e.target.value)}
            onBlur={handleNameSubmit}
            onKeyDown={handleNameKeyDown}
            autoFocus
            className="h-8 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]"
            aria-label="Edit node name"
          />
        ) : (
          <h2
            className="text-base font-medium text-[#EDEDF0] cursor-pointer hover:text-[#5E6AD2] transition-colors truncate"
            onClick={startEditingName}
            role="button"
            aria-label={`Node name: ${displayName}. Click to edit`}
          >
            {displayName}
          </h2>
        )}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onClose}
          className="w-8 h-8 text-[#9292A0] hover:text-[#EDEDF0] hover:bg-[#22222A]"
          aria-label="Close inspector panel"
        >
          <X className="w-4 h-4" />
        </Button>
      </div>

      {/* Tab Bar */}
      <div
        className="h-9 flex items-center px-2 border-b border-[#2D2D35] gap-1 shrink-0 overflow-x-auto"
        role="tablist"
        aria-label="Inspector tabs"
      >
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`tabpanel-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={`h-full px-3 text-[12px] font-medium whitespace-nowrap transition-colors border-b-2 flex items-center gap-1.5 ${
                activeTab === tab.id
                  ? "text-[#EDEDF0] border-[#5E6AD2]"
                  : "text-[#9292A0] hover:text-[#EDEDF0] border-transparent"
              }`}
            >
              {Icon && <Icon className="w-3.5 h-3.5" />}
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-3 min-h-0">
        {/* Overview Tab */}
        {activeTab === "overview" && (
          <div
            role="tabpanel"
            id="tabpanel-overview"
            aria-label="Overview tab"
            className="space-y-4"
          >
            {/* Name Field */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                Name
              </label>
              <Input
                value={displayName}
                onChange={(e) =>
                  onNodeUpdate(selectedNode.id, { name: e.target.value, label: e.target.value })
                }
                className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]"
                aria-label="Node name"
              />
            </div>

            {/* Step Type (read-only) */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                Step Type
              </label>
              <Badge
                variant="outline"
                className="h-7 px-2.5 text-xs bg-[#22222A] border-[#2D2D35] text-[#9292A0] font-medium"
              >
                {STEP_TYPE_LABELS[stepType]}
              </Badge>
            </div>

            {/* Description Field */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                Description
              </label>
              <Textarea
                placeholder="Add a description for this node..."
                className="min-h-[80px] bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2] resize-vertical"
                aria-label="Node description"
              />
            </div>

            {/* Dynamic fields per step type */}
            {stepType === "linear" && (
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                  Soul
                </label>
                <Select
                  value={nodeData.soulRef ?? ""}
                  onValueChange={(v) => onNodeUpdate(selectedNode.id, { soulRef: v || undefined })}
                >
                  <SelectTrigger className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]">
                    <SelectValue placeholder="Select soul" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                    <SelectItem value="">
                      <span className="text-[#5E5E6B]">No soul</span>
                    </SelectItem>
                    {souls.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.name ?? s.id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {stepType === "fanout" && (
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                  Souls
                </label>
                <div className="space-y-2">
                  {(nodeData.soulRefs ?? []).map((ref) => (
                    <div
                      key={ref}
                      className="flex items-center justify-between gap-2 h-9 px-2.5 bg-[#0D0D12] border border-[#2D2D35] rounded-md"
                    >
                      <span className="text-sm text-[#EDEDF0] truncate">
                        {souls.find((s) => s.id === ref)?.name ?? ref}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() =>
                          onNodeUpdate(selectedNode.id, {
                            soulRefs: (nodeData.soulRefs ?? []).filter((r) => r !== ref),
                          })
                        }
                        className="w-6 h-6 text-[#9292A0] hover:text-[#E53935]"
                      >
                        <XIcon className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  ))}
                  <Select
                    value=""
                    onValueChange={(v) => {
                      if (!v) return;
                      const current = nodeData.soulRefs ?? [];
                      if (current.includes(v)) return;
                      onNodeUpdate(selectedNode.id, { soulRefs: [...current, v] });
                    }}
                  >
                    <SelectTrigger className="h-9 bg-[#0D0D12] border-dashed border-[#2D2D35] text-[#5E5E6B] text-sm hover:border-[#5E6AD2] hover:text-[#5E6AD2]">
                    <SelectValue placeholder="Add soul" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                      {souls
                        .filter((s) => !(nodeData.soulRefs ?? []).includes(s.id))
                        .map((s) => (
                          <SelectItem key={s.id} value={s.id}>
                            {s.name ?? s.id}
                          </SelectItem>
                        ))}
                      {souls.filter((s) => !(nodeData.soulRefs ?? []).includes(s.id)).length === 0 && (
                        <SelectItem value="_none" disabled>
                          All souls added
                        </SelectItem>
                      )}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}

            {stepType === "debate" && (
              <>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Soul A
                  </label>
                  <Select
                    value={nodeData.soulARef ?? ""}
                    onValueChange={(v) =>
                      onNodeUpdate(selectedNode.id, { soulARef: v || undefined })
                    }
                  >
                    <SelectTrigger className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]">
                      <SelectValue placeholder="Select soul A" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                      <SelectItem value="">
                        <span className="text-[#5E5E6B]">No soul</span>
                      </SelectItem>
                      {souls.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.name ?? s.id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Soul B
                  </label>
                  <Select
                    value={nodeData.soulBRef ?? ""}
                    onValueChange={(v) =>
                      onNodeUpdate(selectedNode.id, { soulBRef: v || undefined })
                    }
                  >
                    <SelectTrigger className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]">
                      <SelectValue placeholder="Select soul B" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                      <SelectItem value="">
                        <span className="text-[#5E5E6B]">No soul</span>
                      </SelectItem>
                      {souls.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.name ?? s.id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Iterations
                  </label>
                  <Input
                    type="number"
                    min={1}
                    value={nodeData.iterations ?? ""}
                    onChange={(e) => {
                      const v = e.target.value;
                      onNodeUpdate(selectedNode.id, {
                        iterations: v === "" ? undefined : parseInt(v, 10),
                      });
                    }}
                    placeholder="e.g. 2"
                    className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]"
                  />
                </div>
              </>
            )}

            {stepType === "message_bus" && (
              <>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Souls
                  </label>
                  <div className="space-y-2">
                    {(nodeData.soulRefs ?? []).map((ref) => (
                      <div
                        key={ref}
                        className="flex items-center justify-between gap-2 h-9 px-2.5 bg-[#0D0D12] border border-[#2D2D35] rounded-md"
                      >
                        <span className="text-sm text-[#EDEDF0] truncate">
                          {souls.find((s) => s.id === ref)?.name ?? ref}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() =>
                            onNodeUpdate(selectedNode.id, {
                              soulRefs: (nodeData.soulRefs ?? []).filter((r) => r !== ref),
                            })
                          }
                          className="w-6 h-6 text-[#9292A0] hover:text-[#E53935]"
                        >
                          <XIcon className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    ))}
                    <Select
                      value=""
                      onValueChange={(v) => {
                        if (!v || v === "_none") return;
                        const current = nodeData.soulRefs ?? [];
                        if (current.includes(v)) return;
                        onNodeUpdate(selectedNode.id, { soulRefs: [...current, v] });
                      }}
                    >
                      <SelectTrigger className="h-9 bg-[#0D0D12] border-dashed border-[#2D2D35] text-[#5E5E6B] text-sm hover:border-[#5E6AD2] hover:text-[#5E6AD2]">
                        <SelectValue placeholder="Add soul" />
                      </SelectTrigger>
                      <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                        {souls
                          .filter((s) => !(nodeData.soulRefs ?? []).includes(s.id))
                          .map((s) => (
                            <SelectItem key={s.id} value={s.id}>
                              {s.name ?? s.id}
                            </SelectItem>
                          ))}
                        {souls.filter((s) => !(nodeData.soulRefs ?? []).includes(s.id)).length === 0 && (
                          <SelectItem value="_none" disabled>
                            All souls added
                          </SelectItem>
                        )}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Iterations
                  </label>
                  <Input
                    type="number"
                    min={1}
                    value={nodeData.iterations ?? ""}
                    onChange={(e) => {
                      const v = e.target.value;
                      onNodeUpdate(selectedNode.id, {
                        iterations: v === "" ? undefined : parseInt(v, 10),
                      });
                    }}
                    placeholder="e.g. 2"
                    className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]"
                  />
                </div>
              </>
            )}

            {stepType === "router" && (
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                  Soul
                </label>
                <Select
                  value={nodeData.soulRef ?? ""}
                  onValueChange={(v) =>
                    onNodeUpdate(selectedNode.id, { soulRef: v || undefined })
                  }
                >
                  <SelectTrigger className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]">
                    <SelectValue placeholder="Select soul" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                    <SelectItem value="">
                      <span className="text-[#5E5E6B]">No soul</span>
                    </SelectItem>
                    {souls.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.name ?? s.id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {stepType === "gate" && (
              <>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Soul
                  </label>
                  <Select
                    value={nodeData.soulRef ?? ""}
                    onValueChange={(v) =>
                      onNodeUpdate(selectedNode.id, { soulRef: v || undefined })
                    }
                  >
                    <SelectTrigger className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]">
                      <SelectValue placeholder="Select soul" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                      <SelectItem value="">
                        <span className="text-[#5E5E6B]">No soul</span>
                      </SelectItem>
                      {souls.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.name ?? s.id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Eval Key
                  </label>
                  <Select
                    value={nodeData.evalKey ?? ""}
                    onValueChange={(v) =>
                      onNodeUpdate(selectedNode.id, { evalKey: v || undefined })
                    }
                  >
                    <SelectTrigger className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]">
                      <SelectValue placeholder="Select block ID" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                      <SelectItem value="">
                        <span className="text-[#5E5E6B]">None</span>
                      </SelectItem>
                      {workflowNodes
                        .filter((n) => n.id !== selectedNode.id)
                        .map((n) => (
                          <SelectItem key={n.id} value={n.id}>
                            {n.name}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Extract Field
                  </label>
                  <Input
                    value={nodeData.extractField ?? ""}
                    onChange={(e) =>
                      onNodeUpdate(selectedNode.id, {
                        extractField: e.target.value || undefined,
                      })
                    }
                    placeholder="e.g. soul_a"
                    className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]"
                  />
                </div>
              </>
            )}

            {stepType === "synthesize" && (
              <>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Soul
                  </label>
                  <Select
                    value={nodeData.soulRef ?? ""}
                    onValueChange={(v) =>
                      onNodeUpdate(selectedNode.id, { soulRef: v || undefined })
                    }
                  >
                    <SelectTrigger className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]">
                      <SelectValue placeholder="Select soul" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                      <SelectItem value="">
                        <span className="text-[#5E5E6B]">No soul</span>
                      </SelectItem>
                      {souls.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.name ?? s.id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Input Block IDs
                  </label>
                  <div className="space-y-2">
                    {(nodeData.inputBlockIds ?? []).map((blockId) => (
                      <div
                        key={blockId}
                        className="flex items-center justify-between gap-2 h-9 px-2.5 bg-[#0D0D12] border border-[#2D2D35] rounded-md"
                      >
                        <span className="text-sm text-[#EDEDF0] truncate">
                          {workflowNodes.find((n) => n.id === blockId)?.name ?? blockId}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() =>
                            onNodeUpdate(selectedNode.id, {
                              inputBlockIds: (nodeData.inputBlockIds ?? []).filter(
                                (id) => id !== blockId
                              ),
                            })
                          }
                          className="w-6 h-6 text-[#9292A0] hover:text-[#E53935]"
                        >
                          <XIcon className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    ))}
                    <Select
                      value=""
                      onValueChange={(v) => {
                        if (!v || v === "_none") return;
                        const current = nodeData.inputBlockIds ?? [];
                        if (current.includes(v)) return;
                        onNodeUpdate(selectedNode.id, {
                          inputBlockIds: [...current, v],
                        });
                      }}
                    >
                      <SelectTrigger className="h-9 bg-[#0D0D12] border-dashed border-[#2D2D35] text-[#5E5E6B] text-sm hover:border-[#5E6AD2] hover:text-[#5E6AD2]">
                        <SelectValue placeholder="Add block" />
                      </SelectTrigger>
                      <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                        {workflowNodes
                          .filter(
                            (n) =>
                              n.id !== selectedNode.id &&
                              !(nodeData.inputBlockIds ?? []).includes(n.id)
                          )
                          .map((n) => (
                            <SelectItem key={n.id} value={n.id}>
                              {n.name}
                            </SelectItem>
                          ))}
                        {workflowNodes.filter(
                          (n) =>
                            n.id !== selectedNode.id &&
                            !(nodeData.inputBlockIds ?? []).includes(n.id)
                        ).length === 0 && (
                          <SelectItem value="_none" disabled>
                            No blocks available
                          </SelectItem>
                        )}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </>
            )}

            {stepType === "workflow" && (
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                  Workflow Ref
                </label>
                <Input
                  value={nodeData.workflowRef ?? ""}
                  onChange={(e) =>
                    onNodeUpdate(selectedNode.id, {
                      workflowRef: e.target.value || undefined,
                    })
                  }
                  placeholder="e.g. workflow_id or path"
                  className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]"
                />
              </div>
            )}

            {stepType === "retry" && (
              <>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Inner Block Ref
                  </label>
                  <Select
                    value={nodeData.innerBlockRef ?? ""}
                    onValueChange={(v) =>
                      onNodeUpdate(selectedNode.id, { innerBlockRef: v || undefined })
                    }
                  >
                    <SelectTrigger className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]">
                      <SelectValue placeholder="Select block" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                      <SelectItem value="">
                        <span className="text-[#5E5E6B]">None</span>
                      </SelectItem>
                      {workflowNodes
                        .filter((n) => n.id !== selectedNode.id)
                        .map((n) => (
                          <SelectItem key={n.id} value={n.id}>
                            {n.name}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Max Retries
                  </label>
                  <Input
                    type="number"
                    min={0}
                    value={nodeData.maxRetries ?? ""}
                    onChange={(e) => {
                      const v = e.target.value;
                      onNodeUpdate(selectedNode.id, {
                        maxRetries: v === "" ? undefined : parseInt(v, 10),
                      });
                    }}
                    placeholder="e.g. 3"
                    className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]"
                  />
                </div>
              </>
            )}

            {stepType === "team_lead" && (
              <>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Soul
                  </label>
                  <Select
                    value={nodeData.soulRef ?? ""}
                    onValueChange={(v) =>
                      onNodeUpdate(selectedNode.id, { soulRef: v || undefined })
                    }
                  >
                    <SelectTrigger className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]">
                      <SelectValue placeholder="Select soul" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                      <SelectItem value="">
                        <span className="text-[#5E5E6B]">No soul</span>
                      </SelectItem>
                      {souls.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.name ?? s.id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Failure Context Keys
                  </label>
                  <Input
                    value={(nodeData.failureContextKeys ?? []).join(", ")}
                    onChange={(e) =>
                      onNodeUpdate(selectedNode.id, {
                        failureContextKeys: e.target.value
                          ? e.target.value.split(",").map((k) => k.trim()).filter(Boolean)
                          : undefined,
                      })
                    }
                    placeholder="e.g. key1, key2"
                    className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]"
                  />
                </div>
              </>
            )}

            {stepType === "engineering_manager" && (
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                  Soul
                </label>
                <Select
                  value={nodeData.soulRef ?? ""}
                  onValueChange={(v) =>
                    onNodeUpdate(selectedNode.id, { soulRef: v || undefined })
                  }
                >
                  <SelectTrigger className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]">
                    <SelectValue placeholder="Select soul" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                    <SelectItem value="">
                      <span className="text-[#5E5E6B]">No soul</span>
                    </SelectItem>
                    {souls.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.name ?? s.id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {stepType === "file_writer" && (
              <>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Output Path
                  </label>
                  <Input
                    value={nodeData.outputPath ?? ""}
                    onChange={(e) =>
                      onNodeUpdate(selectedNode.id, {
                        outputPath: e.target.value || undefined,
                      })
                    }
                    placeholder="e.g. output/report.md"
                    className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Content Key
                  </label>
                  <Input
                    value={nodeData.contentKey ?? ""}
                    onChange={(e) =>
                      onNodeUpdate(selectedNode.id, {
                        contentKey: e.target.value || undefined,
                      })
                    }
                    placeholder="e.g. report_content"
                    className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]"
                  />
                </div>
              </>
            )}

            {/* Status */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                Status
              </label>
              <StatusBadge status={statusInfo.variant} label={statusInfo.label} />
            </div>

            {/* Tags */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                Tags
              </label>
              <div className="flex flex-wrap gap-2">
                <Badge
                  variant="outline"
                  className="h-6 px-2 text-xs bg-[#22222A] border-[#2D2D35] text-[#9292A0] hover:border-[#5E6AD2] hover:text-[#5E6AD2] cursor-pointer transition-colors"
                >
                  <Plus className="w-3 h-3 mr-1" />
                  Add
                </Badge>
              </div>
            </div>
          </div>
        )}

        {/* Prompt Tab */}
        {activeTab === "prompt" && (
          <div
            role="tabpanel"
            id="tabpanel-prompt"
            aria-label="Prompt tab"
            className="space-y-4"
          >
            {/* Version Selector */}
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B]">
                Prompt
              </label>
              <div className="flex items-center gap-2">
                <Badge className="bg-[rgba(94,106,210,0.12)] text-[#5E6AD2] text-[11px] font-semibold border-0">
                  v1
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs text-[#9292A0] hover:text-[#EDEDF0] hover:bg-[#22222A]"
                >
                  <ChevronDown className="w-3 h-3 mr-1" />
                  Current
                </Button>
              </div>
            </div>

            {/* Improve with AI Button */}
            <Button
              variant="outline"
              className="w-full h-8 border-dashed border-[#5E6AD2]/50 text-[#5E6AD2] hover:bg-[rgba(94,106,210,0.1)] hover:text-[#5E6AD2] text-sm"
              disabled
              aria-label="Improve prompt with AI - Coming soon"
              title="Coming soon"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              Improve with AI
            </Button>

            {/* Prompt Editor */}
            <Textarea
              placeholder="# System Prompt\nYou are a helpful AI assistant...\n\nEdit this prompt to customize the agent's behavior."
              className="min-h-[240px] bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] font-mono text-[13px] leading-relaxed focus:border-[#5E6AD2] resize-vertical"
              spellCheck={false}
              aria-label="Prompt editor"
            />

            {/* Variables Section */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                Available Variables
              </label>
              <div className="flex flex-wrap gap-2">
                <Badge
                  variant="outline"
                  className="h-6 px-2 text-xs bg-[#0D0D12] border-[#2D2D35] text-[#9292A0] hover:border-[#5E6AD2] hover:text-[#5E6AD2] cursor-pointer transition-colors font-mono"
                >
                  {"{{input.data}}"}
                </Badge>
                <Badge
                  variant="outline"
                  className="h-6 px-2 text-xs bg-[#0D0D12] border-[#2D2D35] text-[#9292A0] hover:border-[#5E6AD2] hover:text-[#5E6AD2] cursor-pointer transition-colors font-mono"
                >
                  {"{{workflow.name}}"}
                </Badge>
              </div>
            </div>
          </div>
        )}

        {/* Conditions Tab */}
        {activeTab === "conditions" && (
          <div
            role="tabpanel"
            id="tabpanel-conditions"
            aria-label="Conditions tab"
            className="space-y-4"
          >
            {/* Mode Selector */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                Condition Mode
              </label>
              <div className="flex items-center p-1 bg-[#0D0D12] border border-[#2D2D35] rounded-md">
                {([
                  { mode: "simple" as ConditionMode, icon: FileJson, label: "Simple" },
                  { mode: "expression" as ConditionMode, icon: Code2, label: "Expression" },
                  { mode: "python" as ConditionMode, icon: Terminal, label: "Python" },
                ]).map(({ mode, icon: Icon, label }) => (
                  <button
                    key={mode}
                    onClick={() => setConditionMode(mode)}
                    className={`flex-1 h-7 flex items-center justify-center gap-1.5 text-[12px] font-medium rounded-sm transition-colors ${
                      conditionMode === mode
                        ? "bg-[#22222A] text-[#EDEDF0]"
                        : "text-[#9292A0] hover:text-[#EDEDF0] hover:bg-[rgba(255,255,255,0.04)]"
                    }`}
                    aria-pressed={conditionMode === mode}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Simple Mode */}
            {conditionMode === "simple" && (
              <div className="space-y-4">
                {/* Conditions List */}
                {simpleConditions.map((condition, index) => (
                  <div
                    key={condition.id}
                    className="p-3 bg-[#0D0D12] border border-[#2D2D35] rounded-md space-y-3"
                  >
                    {/* Condition Header */}
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-semibold text-[#5E6AD2] uppercase tracking-wider">
                        Condition {index + 1}
                      </span>
                      {simpleConditions.length > 1 && (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => removeSimpleCondition(condition.id)}
                          className="w-6 h-6 text-[#9292A0] hover:text-[#E53935] hover:bg-[rgba(229,57,53,0.12)]"
                        >
                          <XIcon className="w-3.5 h-3.5" />
                        </Button>
                      )}
                    </div>

                    {/* IF Row */}
                    <div className="flex items-center gap-2 h-10">
                      <span className="w-12 text-[11px] font-semibold text-[#5E6AD2] uppercase tracking-wider">
                        IF
                      </span>
                      <Select
                        value={condition.type}
                        onValueChange={(value) =>
                          updateSimpleCondition(condition.id, "type", value as ConditionType)
                        }
                      >
                        <SelectTrigger className="flex-1 h-9 bg-[#16161C] border-[#2D2D35] text-[#EDEDF0] text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                          {CONDITION_TYPES.map((type) => (
                            <SelectItem key={type.value} value={type.value}>
                              {type.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {/* Operator and Value Row */}
                    <div className="flex items-center gap-2 h-10">
                      <span className="w-12 text-[11px] font-semibold text-[#5E5E6B] uppercase tracking-wider">
                        &nbsp;
                      </span>
                      <Select
                        value={condition.operator}
                        onValueChange={(value) =>
                          updateSimpleCondition(condition.id, "operator", value as ConditionOperator)
                        }
                      >
                        <SelectTrigger className="h-9 bg-[#16161C] border-[#2D2D35] text-[#EDEDF0] text-sm w-[110px]">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                          {OPERATORS.map((op) => (
                            <SelectItem key={op.value} value={op.value}>
                              {op.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Input
                        value={condition.value}
                        onChange={(e) =>
                          updateSimpleCondition(condition.id, "value", e.target.value)
                        }
                        placeholder="value"
                        className="flex-1 h-9 bg-[#16161C] border-[#2D2D35] text-[#EDEDF0] text-sm"
                      />
                    </div>

                    {/* THEN Row */}
                    <div className="flex items-center gap-2 h-10">
                      <span className="w-12 text-[11px] font-semibold text-[#5E6AD2] uppercase tracking-wider">
                        THEN
                      </span>
                      <span className="text-sm text-[#9292A0]">go to</span>
                      <Select
                        value={condition.thenStep}
                        onValueChange={(value) =>
                          updateSimpleCondition(condition.id, "thenStep", value || "next")
                        }
                      >
                        <SelectTrigger className="flex-1 h-9 bg-[#16161C] border-[#2D2D35] text-[#EDEDF0] text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                          {availableSteps.map((step) => (
                            <SelectItem key={step.value} value={step.value}>
                              {step.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {/* ELSE Row */}
                    <div className="flex items-center gap-2 h-10">
                      <span className="w-12 text-[11px] font-semibold text-[#5E6AD2] uppercase tracking-wider">
                        ELSE
                      </span>
                      <span className="text-sm text-[#9292A0]">go to</span>
                      <Select
                        value={condition.elseStep}
                        onValueChange={(value) =>
                          updateSimpleCondition(condition.id, "elseStep", value || "end")
                        }
                      >
                        <SelectTrigger className="flex-1 h-9 bg-[#16161C] border-[#2D2D35] text-[#EDEDF0] text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                          {availableSteps.map((step) => (
                            <SelectItem key={step.value} value={step.value}>
                              {step.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                ))}

                {/* Add Condition Button */}
                <Button
                  variant="outline"
                  onClick={addSimpleCondition}
                  className="w-full h-8 border-dashed border-[#2D2D35] text-[#9292A0] hover:border-[#5E6AD2] hover:text-[#5E6AD2] text-xs"
                >
                  <Plus className="w-3.5 h-3.5 mr-1.5" />
                  Add condition
                </Button>
              </div>
            )}

            {/* Expression Mode */}
            {conditionMode === "expression" && (
              <div className="space-y-4">
                {/* Expression Editor */}
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Expression (Jinja2)
                  </label>
                  <div className="relative">
                    <Textarea
                      value={expressionValue}
                      onChange={handleExpressionChange}
                      onFocus={() => setShowAutocomplete(true)}
                      placeholder="{{ outputs.step_name.result }} >= 7 and {{ artifacts.data }} != null"
                      className="min-h-[160px] bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] font-mono text-[13px] leading-relaxed focus:border-[#5E6AD2] resize-vertical pr-20"
                      spellCheck={false}
                      aria-label="Expression (Jinja2)"
                    />
                    {/* Validation Indicator */}
                    <div
                      className={cn(
                        "absolute bottom-2 right-2 flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium",
                        expressionValidation.isValid
                          ? "bg-[rgba(40,167,69,0.12)] text-[#28A745]"
                          : "bg-[rgba(229,57,53,0.12)] text-[#E53935]"
                      )}
                    >
                      {expressionValidation.isValid ? (
                        <>
                          <Check className="w-3.5 h-3.5" />
                          <span>Valid</span>
                        </>
                      ) : (
                        <>
                          <XIcon className="w-3.5 h-3.5" />
                          <span>Invalid</span>
                        </>
                      )}
                    </div>
                  </div>
                  {/* Error Message */}
                  {!expressionValidation.isValid && expressionValidation.message && (
                    <p className="mt-1.5 text-[11px] text-[#E53935]">
                      {expressionValidation.message}
                    </p>
                  )}
                </div>

                {/* Autocomplete Popup */}
                {showAutocomplete && (
                  <div className="p-2 bg-[#22222A] border border-[#2D2D35] rounded-md">
                    <div className="text-[11px] text-[#5E5E6B] mb-1.5 font-medium">
                      Available variables — click to insert
                    </div>
                    <div className="space-y-0.5 max-h-[140px] overflow-y-auto">
                      {AVAILABLE_VARIABLES.map((variable) => (
                        <button
                          key={variable}
                          onClick={() => insertVariable(variable)}
                          className="w-full text-left px-2 py-1.5 text-[12px] font-mono text-[#9292A0] hover:bg-[#0D0D12] hover:text-[#5E6AD2] rounded transition-colors"
                        >
                          {`{{ ${variable} }}`}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Branch Configuration */}
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Outgoing Branches
                  </label>
                  <div className="p-3 bg-[#0D0D12] border border-[#2D2D35] rounded-md space-y-3">
                    {/* True Branch */}
                    <div className="flex items-center gap-3 h-10">
                      <span className="w-14 text-[11px] font-semibold text-[#5E6AD2] uppercase tracking-wider">
                        IF TRUE
                      </span>
                      <Select defaultValue="next">
                        <SelectTrigger className="flex-1 h-9 bg-[#16161C] border-[#2D2D35] text-[#EDEDF0] text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                          {availableSteps.map((step) => (
                            <SelectItem key={step.value} value={step.value}>
                              {step.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    {/* False Branch */}
                    <div className="flex items-center gap-3 h-10">
                      <span className="w-14 text-[11px] font-semibold text-[#5E6AD2] uppercase tracking-wider">
                        IF FALSE
                      </span>
                      <Select defaultValue="end">
                        <SelectTrigger className="flex-1 h-9 bg-[#16161C] border-[#2D2D35] text-[#EDEDF0] text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                          {availableSteps.map((step) => (
                            <SelectItem key={step.value} value={step.value}>
                              {step.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>

                {/* Last Run Result */}
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Last Run Result
                  </label>
                  <div className="p-3 bg-[rgba(40,167,69,0.08)] border-l-[3px] border-[#28A745] rounded-r-md">
                    <div className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-[#28A745]" />
                      <span className="text-sm text-[#EDEDF0]">
                        Condition evaluated to <strong>TRUE</strong>
                      </span>
                    </div>
                    <div className="mt-1.5 text-[11px] text-[#9292A0] font-mono space-y-0.5">
                      <div>Score: 8.5 {'>'}= 7 ✓</div>
                      <div>Risk: &apos;low&apos; != &apos;high&apos; ✓</div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Python Mode */}
            {conditionMode === "python" && (
              <div className="space-y-4">
                {/* Monaco Editor */}
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Python Script
                  </label>
                  <div className="border border-[#2D2D35] rounded-md overflow-hidden">
                    <Editor
                      height="240px"
                      language="python"
                      value={pythonCode}
                      onChange={(value) => setPythonCode(value || "")}
                      theme="vs-dark"
                      options={{
                        minimap: { enabled: false },
                        fontSize: 13,
                        fontFamily: "JetBrains Mono, monospace",
                        lineNumbers: "on",
                        roundedSelection: false,
                        scrollBeyondLastLine: false,
                        readOnly: false,
                        automaticLayout: true,
                        padding: { top: 12, bottom: 12 },
                        folding: true,
                        renderLineHighlight: "line",
                        matchBrackets: "always",
                        tabSize: 4,
                        insertSpaces: true,
                      }}
                    />
                  </div>
                </div>

                {/* Sandbox Warning */}
                <div className="flex items-start gap-2 p-2.5 bg-[rgba(245,166,35,0.08)] border border-[#F5A623]/30 rounded-md">
                  <AlertCircle className="w-4 h-4 text-[#F5A623] shrink-0 mt-0.5" />
                  <span className="text-xs text-[#EDEDF0] leading-relaxed">
                    Script runs in isolated environment with 5s timeout.
                  </span>
                </div>

                {/* Test Condition Button */}
                <Button
                  variant="outline"
                  onClick={testPythonCondition}
                  disabled={isTestingPython}
                  className="w-full h-9 border-[#3F3F4A] text-[#EDEDF0] hover:bg-[#22222A] hover:text-[#EDEDF0] transition-all duration-150 flex items-center justify-center gap-2"
                >
                  {isTestingPython ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Testing...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      Test Condition
                    </>
                  )}
                </Button>

                {/* Test Result */}
                {pythonTestResult && (
                  <div
                    className={cn(
                      "p-3 border-l-[3px] rounded-r-md",
                      pythonTestResult.success && pythonTestResult.result
                        ? "bg-[rgba(40,167,69,0.08)] border-[#28A745]"
                        : pythonTestResult.success && !pythonTestResult.result
                        ? "bg-[rgba(229,57,53,0.08)] border-[#E53935]"
                        : "bg-[rgba(229,57,53,0.08)] border-[#E53935]"
                    )}
                  >
                    <div className="flex items-center gap-2">
                      {pythonTestResult.success && pythonTestResult.result ? (
                        <>
                          <Check className="w-4 h-4 text-[#28A745]" />
                          <span className="text-sm text-[#EDEDF0]">
                            Result: <strong className="text-[#28A745]">True</strong>
                          </span>
                        </>
                      ) : pythonTestResult.success && !pythonTestResult.result ? (
                        <>
                          <XIcon className="w-4 h-4 text-[#E53935]" />
                          <span className="text-sm text-[#EDEDF0]">
                            Result: <strong className="text-[#E53935]">False</strong>
                          </span>
                        </>
                      ) : (
                        <>
                          <AlertCircle className="w-4 h-4 text-[#E53935]" />
                          <span className="text-sm text-[#EDEDF0]">Error</span>
                        </>
                      )}
                    </div>
                    {pythonTestResult.error && (
                      <p className="mt-1.5 text-[11px] text-[#E53935]">
                        {pythonTestResult.error}
                      </p>
                    )}
                  </div>
                )}

                {/* Branch Configuration */}
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                    Outgoing Branches
                  </label>
                  <div className="p-3 bg-[#0D0D12] border border-[#2D2D35] rounded-md space-y-3">
                    <div className="flex items-center gap-3 h-10">
                      <span className="w-14 text-[11px] font-semibold text-[#5E6AD2] uppercase tracking-wider">
                        IF TRUE
                      </span>
                      <Select defaultValue="next">
                        <SelectTrigger className="flex-1 h-9 bg-[#16161C] border-[#2D2D35] text-[#EDEDF0] text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                          {availableSteps.map((step) => (
                            <SelectItem key={step.value} value={step.value}>
                              {step.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-center gap-3 h-10">
                      <span className="w-14 text-[11px] font-semibold text-[#5E6AD2] uppercase tracking-wider">
                        IF FALSE
                      </span>
                      <Select defaultValue="end">
                        <SelectTrigger className="flex-1 h-9 bg-[#16161C] border-[#2D2D35] text-[#EDEDF0] text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#22222A] border-[#2D2D35]">
                          {availableSteps.map((step) => (
                            <SelectItem key={step.value} value={step.value}>
                              {step.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Incoming Conditions (read-only) */}
            {incomingConditions.length > 0 && (
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                  Incoming Connections
                </label>
                <div className="space-y-2">
                  {incomingConditions.map((condition) => (
                    <div
                      key={condition.id}
                      className="flex items-center gap-3 p-2.5 bg-[#0D0D12] border border-[#2D2D35] rounded-md"
                    >
                      <ArrowLeft className="w-4 h-4 text-[#3F3F4A]" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-[#EDEDF0] truncate">
                          {condition.fromNode}
                        </div>
                        <div className="text-[11px] text-[#5E5E6B] capitalize">
                          {condition.type === "sequential" ? "Sequential flow" : "Conditional branch"}
                          {condition.condition && ` • ${condition.condition}`}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Empty Incoming Conditions State */}
            {incomingConditions.length === 0 && (
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                  Incoming Connections
                </label>
                <div className="p-3 bg-[#0D0D12] border border-[#2D2D35] border-dashed rounded-md text-center">
                  <p className="text-xs text-[#5E5E6B]">
                    No incoming connections
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Execution Tab */}
        {activeTab === "execution" && (
          <div
            role="tabpanel"
            id="tabpanel-execution"
            aria-label="Execution tab"
            className="space-y-4"
          >
            {/* Status */}
            <div className={cn(
              "mb-4 p-3 rounded-md border",
              isExecuting
                ? "bg-[rgba(0,229,255,0.05)] border-[#00E5FF]/20"
                : status === "completed"
                ? "bg-[rgba(40,167,69,0.05)] border-[#28A745]/20"
                : status === "failed"
                ? "bg-[rgba(229,57,53,0.05)] border-[#E53935]/20"
                : "bg-[#0D0D12] border-[#2D2D35]"
            )}>
              <div className="flex items-center gap-2 mb-2">
                {isExecuting ? (
                  <span className="w-1.5 h-1.5 rounded-full bg-[#00E5FF] animate-pulse" />
                ) : status === "completed" ? (
                  <span className="w-1.5 h-1.5 rounded-full bg-[#28A745]" />
                ) : status === "failed" ? (
                  <span className="w-1.5 h-1.5 rounded-full bg-[#E53935]" />
                ) : (
                  <span className="w-1.5 h-1.5 rounded-full bg-[#9292A0]" />
                )}
                <span className={cn(
                  "text-sm font-medium",
                  isExecuting
                    ? "text-[#00E5FF]"
                    : status === "completed"
                    ? "text-[#28A745]"
                    : status === "failed"
                    ? "text-[#E53935]"
                    : "text-[#9292A0]"
                )}>
                  {isExecuting ? "Running" :
                   status === "completed" ? "Completed" :
                   status === "failed" ? "Failed" :
                   status === "pending" ? "Pending" : "Idle"}
                </span>
              </div>
              {/* Duration - live during execution, final when complete */}
              <div className="font-mono text-xs text-[#9292A0]">
                Duration: {formatElapsedTime(isExecuting ? elapsedTime : finalDuration)}
              </div>
            </div>

            {/* Cost - final cost when complete, current cost when running */}
            <div className="mb-4">
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                {executionComplete ? "Final Cost" : "Current Cost"}
              </label>
              <div className="flex items-center justify-between p-2 rounded-md bg-[#0D0D12] border border-[#2D2D35]">
                <span className="font-mono text-sm text-[#EDEDF0]">
                  ${(nodeData.executionCost || 0).toFixed(3)}
                </span>
                {nodeData.cost && !executionComplete && (
                  <span className="text-xs text-[#5E5E6B]">
                    ~${nodeData.cost.toFixed(2)} estimated
                  </span>
                )}
              </div>
            </div>

            {/* Total Tokens - show actual when complete */}
            {executionComplete && (
              <div className="mb-4">
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                  Total Tokens
                </label>
                <div className="flex items-center justify-between p-2 rounded-md bg-[#0D0D12] border border-[#2D2D35]">
                  <span className="font-mono text-sm text-[#EDEDF0]">
                    {nodeData.executionCost
                      ? Math.round(nodeData.executionCost * 10000).toLocaleString()
                      : "--"}
                  </span>
                </div>
              </div>
            )}

            {/* Token Usage (placeholder) */}
            <div className="mb-4">
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                Token Usage
              </label>
              <div className="p-3 rounded-md bg-[#0D0D12] border border-[#2D2D35]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-[#9292A0]">Input: --</span>
                  <span className="text-xs text-[#9292A0]">Output: --</span>
                </div>
                <div className="h-1.5 bg-[#2D2D35] rounded-full overflow-hidden">
                  <div className="h-full w-[0%] bg-[#5E6AD2] rounded-full" />
                </div>
              </div>
            </div>

            {/* Latest Output (placeholder) */}
            <div className="mb-4">
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                Latest Output
              </label>
              <div className="p-3 rounded-md bg-[#0D0D12] border border-[#2D2D35] font-mono text-xs text-[#9292A0] leading-relaxed">
                {status === "running" ? (
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Processing...
                  </div>
                ) : status === "completed" ? (
                  "Execution completed successfully.\nCheck logs for full output."
                ) : status === "failed" ? (
                  <span className="text-[#E53935]">Execution failed. Check logs for error details.</span>
                ) : (
                  "Waiting for execution..."
                )}
              </div>
            </div>

            {/* Recent Logs for this node */}
            {executionLogs.length > 0 && (
              <div className="mb-4">
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                  Recent Logs
                </label>
                <div className="space-y-1 max-h-[120px] overflow-y-auto">
                  {executionLogs
                    .filter((log) => log.nodeId === selectedNode!.id)
                    .slice(-5)
                    .map((log) => (
                      <div
                        key={log.id}
                        className="text-xs font-mono text-[#9292A0] truncate"
                      >
                        <span
                          className={cn(
                            "text-[10px] mr-2",
                            log.level === "ERROR"
                              ? "text-[#E53935]"
                              : log.level === "WARN"
                              ? "text-[#F5A623]"
                              : "text-[#9292A0]"
                          )}
                        >
                          {log.level}
                        </span>
                        {log.message}
                      </div>
                    ))}
                  {executionLogs.filter((log) => log.nodeId === selectedNode!.id).length === 0 && (
                    <div className="text-xs text-[#5E5E6B]">No logs for this node yet</div>
                  )}
                </div>
              </div>
            )}

            {/* Runtime Controls */}
            {isExecuting && (
              <div className="pt-3 border-t border-[#2D2D35] space-y-3">
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B]">
                  Runtime Controls
                </label>

                {/* Button Row */}
                <div className="grid grid-cols-3 gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onPause}
                    className="h-9 rounded text-xs font-medium flex items-center justify-center gap-1 border-[#F5A623] text-[#F5A623] hover:bg-[rgba(245,166,35,0.12)]"
                  >
                    <Pause className="w-3 h-3" />
                    Pause
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onKill}
                    className="h-9 rounded text-xs font-medium flex items-center justify-center gap-1 border-[#E53935] text-[#E53935] hover:bg-[rgba(229,57,53,0.12)]"
                  >
                    <Square className="w-3 h-3" />
                    Kill
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onRestart}
                    className="h-9 rounded text-xs font-medium flex items-center justify-center gap-1 border-[#3F3F4A] text-[#EDEDF0] hover:bg-[#22222A]"
                  >
                    <RotateCcw className="w-3 h-3" />
                    Restart
                  </Button>
                </div>

                {/* Message Agent */}
                <div>
                  <label className="block text-xs text-[#9292A0] mb-2">
                    Message Agent
                  </label>
                  <div className="flex gap-2">
                    <Input
                      type="text"
                      value={messageText}
                      onChange={(e) => setMessageText(e.target.value)}
                      placeholder="Type message..."
                      className="h-9 bg-[#0D0D12] border-[#2D2D35] text-[#EDEDF0] text-sm focus:border-[#5E6AD2]"
                    />
                    <Button
                      size="sm"
                      disabled={!messageText.trim()}
                      onClick={() => {
                        console.log("Message to agent:", messageText);
                        setMessageText("");
                      }}
                      className="h-9 px-3 bg-[#5E6AD2] hover:bg-[#717EE3] text-white disabled:opacity-50"
                    >
                      <Send className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                {/* Info Banner */}
                <div className="flex items-start gap-2 p-2 rounded-md bg-[rgba(245,166,35,0.05)] border-l-[3px] border-[#F5A623]">
                  <AlertCircle className="w-4 h-4 text-[#F5A623] shrink-0 mt-0.5" />
                  <span className="text-xs text-[#EDEDF0]">
                    Edits will apply on restart
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Audit Tab */}
        {activeTab === "audit" && (
          <div
            role="tabpanel"
            id="tabpanel-audit"
            aria-label="Audit tab"
            className="space-y-4"
          >
            {Array.isArray(nodeData.audit_log) && nodeData.audit_log.length > 0 ? (
              <div className="space-y-2">
                {(nodeData.audit_log as { timestamp: string; action: string; actor: string; detail: string }[])
                  .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
                  .map((entry, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 bg-[#0D0D12] border border-[#2D2D35] rounded-md space-y-1.5"
                    >
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className={cn(
                            "inline-flex h-5 px-2 rounded text-[11px] font-medium",
                            entry.action.toLowerCase().includes("edited") && "bg-[rgba(94,106,210,0.12)] text-[#5E6AD2]",
                            entry.action.toLowerCase().includes("paused") && "bg-[rgba(245,166,35,0.12)] text-[#F5A623]",
                            entry.action.toLowerCase().includes("resumed") && "bg-[rgba(40,167,69,0.12)] text-[#28A745]",
                            entry.action.toLowerCase().includes("killed") && "bg-[rgba(229,57,53,0.12)] text-[#E53935]",
                            entry.action.toLowerCase().includes("message") && "bg-[rgba(0,229,255,0.12)] text-[#00E5FF]",
                            entry.action.toLowerCase().includes("restarted") && "bg-[rgba(94,106,210,0.12)] text-[#5E6AD2]",
                            !["edited", "paused", "resumed", "killed", "message", "restarted"].some((k) =>
                              entry.action.toLowerCase().includes(k)
                            ) && "bg-[rgba(146,146,160,0.12)] text-[#9292A0]"
                          )}
                        >
                          {entry.action}
                        </span>
                        <span className="text-[11px] text-[#5E5E6B] font-mono">
                          {new Date(entry.timestamp).toLocaleString()}
                        </span>
                      </div>
                      {entry.actor && (
                        <div className="text-xs text-[#9292A0]">
                          {entry.actor}
                        </div>
                      )}
                      {entry.detail && (
                        <div className="text-xs text-[#EDEDF0] truncate" title={entry.detail}>
                          {entry.detail}
                        </div>
                      )}
                    </div>
                  ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <History className="w-10 h-10 text-[#3F3F4A] mb-3" />
                <p className="text-sm text-[#5E5E6B]">No modifications recorded</p>
              </div>
            )}
          </div>
        )}

        {/* Versions Tab */}
        {activeTab === "versions" && (
          <div
            role="tabpanel"
            id="tabpanel-versions"
            aria-label="Versions tab"
            className="space-y-4"
          >
            {Array.isArray(nodeData.versions) && nodeData.versions.length > 0 ? (
              <div className="space-y-2">
                {(nodeData.versions as { hash: string; message: string; author: string; timestamp: string }[]).map(
                  (v, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 bg-[#0D0D12] border border-[#2D2D35] rounded-md space-y-1.5"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-xs text-[#5E6AD2]">{v.hash.slice(0, 7)}</span>
                        <span className="text-[11px] text-[#5E5E6B]">{formatRelativeTime(v.timestamp)}</span>
                      </div>
                      <div className="text-sm text-[#EDEDF0] line-clamp-2">{v.message}</div>
                      {v.author && (
                        <div className="text-xs text-[#9292A0]">{v.author}</div>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        disabled
                        className="h-7 px-2 text-xs border-[#2D2D35] text-[#9292A0] cursor-not-allowed"
                      >
                        View Diff
                      </Button>
                    </div>
                  )
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <GitBranch className="w-10 h-10 text-[#3F3F4A] mb-3" />
                <p className="text-sm text-[#5E5E6B]">No version history</p>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}

function formatRelativeTime(date: string): string {
  if (!date) return "—";
  const now = new Date();
  const then = new Date(date);
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  const diffWeeks = Math.floor(diffDays / 7);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
  if (diffWeeks < 4) return `${diffWeeks} week${diffWeeks > 1 ? "s" : ""} ago`;
  return then.toLocaleDateString();
}

// Helper function to format elapsed time
function formatElapsedTime(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  const centiseconds = Math.floor((ms % 1000) / 10);
  return `${minutes.toString().padStart(2, "0")}:${remainingSeconds
    .toString()
    .padStart(2, "0")}.${centiseconds.toString().padStart(2, "0")}`;
}

export default InspectorPanel;
