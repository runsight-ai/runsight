import * as RunStatusDotModule from "../../../../../RunStatusDot";
import * as EmptyStateModule from "../../../shared/EmptyState";
import * as BadgeModule from "../../badge";
import * as ButtonModule from "../../button";
import * as CardModule from "../../card";
import * as DialogModule from "../../dialog";
import * as DropdownMenuModule from "../../dropdown-menu";
import * as InputModule from "../../input";
import * as KeyValueModule from "../../key-value";
import * as LabelModule from "../../label";
import * as SelectModule from "../../select";
import * as SegmentedControlModule from "../../segmented-control";
import * as SkeletonModule from "../../skeleton";
import * as SliderModule from "../../slider";
import * as StatCardModule from "../../stat-card";
import * as StatusDotModule from "../../status-dot";
import * as SwitchModule from "../../switch";
import * as TableModule from "../../table";
import * as TabsModule from "../../tabs";
import * as TagInputModule from "../../tag-input";
import * as TextareaModule from "../../textarea";
import * as TooltipModule from "../../tooltip";

export const canonicalSuites = [
  "renderedDisplayContracts.test.tsx",
  "renderedFormControls.test.tsx",
  "renderedNavigationAndOverlays.test.tsx",
] as const;

export type CanonicalSuite = (typeof canonicalSuites)[number];

export const renderedBaselineCoverage = {
  "./RunStatusDot": {
    suite: "renderedDisplayContracts.test.tsx",
    components: ["RunStatusDot"],
  },
  "./badge": {
    suite: "renderedDisplayContracts.test.tsx",
    components: ["Badge", "BadgeDot"],
  },
  "./button": {
    suite: "renderedFormControls.test.tsx",
    components: ["Button"],
  },
  "./card": {
    suite: "renderedDisplayContracts.test.tsx",
    components: [
      "Card",
      "CardAction",
      "CardContent",
      "CardDescription",
      "CardFooter",
      "CardHeader",
      "CardTitle",
    ],
  },
  "./dialog": {
    suite: "renderedNavigationAndOverlays.test.tsx",
    components: [
      "Dialog",
      "DialogBody",
      "DialogClose",
      "DialogContent",
      "DialogDescription",
      "DialogFooter",
      "DialogHeader",
      "DialogOverlay",
      "DialogPortal",
      "DialogTitle",
      "DialogTrigger",
    ],
  },
  "./dropdown-menu": {
    suite: "renderedNavigationAndOverlays.test.tsx",
    components: [
      "DropdownMenu",
      "DropdownMenuCheckboxItem",
      "DropdownMenuContent",
      "DropdownMenuGroup",
      "DropdownMenuItem",
      "DropdownMenuLabel",
      "DropdownMenuPortal",
      "DropdownMenuRadioGroup",
      "DropdownMenuRadioItem",
      "DropdownMenuSeparator",
      "DropdownMenuShortcut",
      "DropdownMenuSub",
      "DropdownMenuSubContent",
      "DropdownMenuSubTrigger",
      "DropdownMenuTrigger",
    ],
  },
  "./empty-state": {
    suite: "renderedDisplayContracts.test.tsx",
    components: ["EmptyState"],
  },
  "./input": {
    suite: "renderedFormControls.test.tsx",
    components: ["Input"],
  },
  "./key-value": {
    suite: "renderedDisplayContracts.test.tsx",
    components: ["KeyValue", "KeyValueList"],
  },
  "./label": {
    suite: "renderedFormControls.test.tsx",
    components: ["Label"],
  },
  "./select": {
    suite: "renderedNavigationAndOverlays.test.tsx",
    components: [
      "Select",
      "SelectContent",
      "SelectGroup",
      "SelectItem",
      "SelectLabel",
      "SelectScrollDownButton",
      "SelectScrollUpButton",
      "SelectSeparator",
      "SelectTrigger",
      "SelectValue",
    ],
  },
  "./segmented-control": {
    suite: "renderedFormControls.test.tsx",
    components: ["SegmentedControl"],
  },
  "./skeleton": {
    suite: "renderedDisplayContracts.test.tsx",
    components: ["Skeleton"],
  },
  "./slider": {
    suite: "renderedFormControls.test.tsx",
    components: ["Slider"],
  },
  "./stat-card": {
    suite: "renderedDisplayContracts.test.tsx",
    components: ["StatCard"],
  },
  "./status-dot": {
    suite: "renderedDisplayContracts.test.tsx",
    components: ["StatusDot"],
  },
  "./switch": {
    suite: "renderedFormControls.test.tsx",
    components: ["Switch"],
  },
  "./table": {
    suite: "renderedNavigationAndOverlays.test.tsx",
    components: [
      "Table",
      "TableBody",
      "TableCaption",
      "TableCell",
      "TableFooter",
      "TableHead",
      "TableHeader",
      "TableMonoCell",
      "TableRow",
    ],
  },
  "./tag-input": {
    suite: "renderedFormControls.test.tsx",
    components: ["TagInput"],
  },
  "./tabs": {
    suite: "renderedNavigationAndOverlays.test.tsx",
    components: ["TabBadge", "Tabs", "TabsContent", "TabsList", "TabsTrigger"],
  },
  "./textarea": {
    suite: "renderedFormControls.test.tsx",
    components: ["Textarea"],
  },
  "./tooltip": {
    suite: "renderedNavigationAndOverlays.test.tsx",
    components: ["SoulTip", "Tooltip", "TooltipContent", "TooltipProvider", "TooltipTrigger"],
  },
} satisfies Record<
  string,
  { suite: CanonicalSuite; components: readonly string[] }
>;

export type CoveredSubpath = keyof typeof renderedBaselineCoverage;

export const componentModules = {
  "./RunStatusDot": RunStatusDotModule,
  "./badge": BadgeModule,
  "./button": ButtonModule,
  "./card": CardModule,
  "./dialog": DialogModule,
  "./dropdown-menu": DropdownMenuModule,
  "./empty-state": EmptyStateModule,
  "./input": InputModule,
  "./key-value": KeyValueModule,
  "./label": LabelModule,
  "./select": SelectModule,
  "./segmented-control": SegmentedControlModule,
  "./skeleton": SkeletonModule,
  "./slider": SliderModule,
  "./stat-card": StatCardModule,
  "./status-dot": StatusDotModule,
  "./switch": SwitchModule,
  "./table": TableModule,
  "./tag-input": TagInputModule,
  "./tabs": TabsModule,
  "./textarea": TextareaModule,
  "./tooltip": TooltipModule,
} satisfies Record<CoveredSubpath, object>;

export const nonComponentNamedExports = {
  "./badge": ["badgeVariants"],
  "./button": ["buttonVariants"],
} satisfies Partial<Record<CoveredSubpath, readonly string[]>>;

export interface RenderedEvidence {
  assertionToken: string;
  testName: string;
}

function evidence(testName: string, assertionToken: string): RenderedEvidence {
  return { testName, assertionToken };
}

export const renderedComponentEvidence: Record<CoveredSubpath, Record<string, RenderedEvidence>> = {
  "./RunStatusDot": {
    RunStatusDot: evidence("maps runtime run statuses onto observable status-dot presentation", "title='running'"),
  },
  "./badge": {
    Badge: evidence("renders badge variants and the decorative badge dot", "data-slot='badge-dot'"),
    BadgeDot: evidence("renders badge variants and the decorative badge dot", "data-slot='badge-dot'"),
  },
  "./button": {
    Button: evidence("disables buttons and exposes a spinner when loading", "aria-busy"),
  },
  "./card": {
    Card: evidence("renders card composition slots and raised interactive styling", "data-slot='card-footer'"),
    CardAction: evidence("renders card composition slots and raised interactive styling", "data-slot='card-footer'"),
    CardContent: evidence("renders card composition slots and raised interactive styling", "data-slot='card-content'"),
    CardDescription: evidence("renders card composition slots and raised interactive styling", "Everything looks healthy."),
    CardFooter: evidence("renders card composition slots and raised interactive styling", "data-slot='card-footer'"),
    CardHeader: evidence("renders card composition slots and raised interactive styling", "data-slot='card-header'"),
    CardTitle: evidence("renders card composition slots and raised interactive styling", "Workflow health"),
  },
  "./dialog": {
    Dialog: evidence(
      "opens dialogs from the trigger and closes them from the built-in footer close affordance",
      "Workflow settings",
    ),
    DialogBody: evidence(
      "opens dialogs from the trigger and closes them from the built-in footer close affordance",
      "Dialog body copy",
    ),
    DialogClose: evidence(
      "opens dialogs from the trigger and closes them from the built-in footer close affordance",
      "Cancel",
    ),
    DialogContent: evidence(
      "opens dialogs from the trigger and closes them from the built-in footer close affordance",
      "data-slot='dialog-content'",
    ),
    DialogDescription: evidence(
      "opens dialogs from the trigger and closes them from the built-in footer close affordance",
      "Choose how this workflow runs.",
    ),
    DialogFooter: evidence(
      "opens dialogs from the trigger and closes them from the built-in footer close affordance",
      "data-slot='dialog-footer'",
    ),
    DialogHeader: evidence(
      "opens dialogs from the trigger and closes them from the built-in footer close affordance",
      "Workflow settings",
    ),
    DialogOverlay: evidence("renders public portal and overlay exports inside their primitive roots", "dialog-overlay"),
    DialogPortal: evidence(
      "renders public portal and overlay exports inside their primitive roots",
      "Manual dialog portal content",
    ),
    DialogTitle: evidence(
      "opens dialogs from the trigger and closes them from the built-in footer close affordance",
      "Workflow settings",
    ),
    DialogTrigger: evidence(
      "opens dialogs from the trigger and closes them from the built-in footer close affordance",
      "Open dialog",
    ),
  },
  "./dropdown-menu": {
    DropdownMenu: evidence(
      "opens dropdown menus, preserves separator/shortcut structure, and invokes clicked items",
      "Actions",
    ),
    DropdownMenuCheckboxItem: evidence(
      "opens dropdown menus, preserves separator/shortcut structure, and invokes clicked items",
      "dropdown-menu-checkbox-item-indicator",
    ),
    DropdownMenuContent: evidence(
      "opens dropdown menus, preserves separator/shortcut structure, and invokes clicked items",
      "data-slot='dropdown-menu-content'",
    ),
    DropdownMenuGroup: evidence(
      "opens dropdown menus, preserves separator/shortcut structure, and invokes clicked items",
      "data-slot='dropdown-menu-group'",
    ),
    DropdownMenuItem: evidence(
      "opens dropdown menus, preserves separator/shortcut structure, and invokes clicked items",
      "Rename",
    ),
    DropdownMenuLabel: evidence(
      "opens dropdown menus, preserves separator/shortcut structure, and invokes clicked items",
      "Workflow actions",
    ),
    DropdownMenuPortal: evidence(
      "renders public portal and overlay exports inside their primitive roots",
      "Manual dropdown portal content",
    ),
    DropdownMenuRadioGroup: evidence(
      "opens dropdown menus, preserves separator/shortcut structure, and invokes clicked items",
      "Canvas mode",
    ),
    DropdownMenuRadioItem: evidence(
      "opens dropdown menus, preserves separator/shortcut structure, and invokes clicked items",
      "dropdown-menu-radio-item-indicator",
    ),
    DropdownMenuSeparator: evidence(
      "opens dropdown menus, preserves separator/shortcut structure, and invokes clicked items",
      "data-slot='dropdown-menu-separator'",
    ),
    DropdownMenuShortcut: evidence(
      "opens dropdown menus, preserves separator/shortcut structure, and invokes clicked items",
      "Cmd+K",
    ),
    DropdownMenuSub: evidence(
      "opens dropdown menus, preserves separator/shortcut structure, and invokes clicked items",
      "More actions",
    ),
    DropdownMenuSubContent: evidence(
      "opens dropdown menus, preserves separator/shortcut structure, and invokes clicked items",
      "Duplicate",
    ),
    DropdownMenuSubTrigger: evidence(
      "opens dropdown menus, preserves separator/shortcut structure, and invokes clicked items",
      "data-slot='dropdown-menu-sub-trigger'",
    ),
    DropdownMenuTrigger: evidence(
      "opens dropdown menus, preserves separator/shortcut structure, and invokes clicked items",
      "Actions",
    ),
  },
  "./empty-state": {
    EmptyState: evidence("renders empty states with optional description and action affordances", "empty-state-icon"),
  },
  "./input": {
    Input: evidence("associates labels with inputs and exposes input state variants", "api-key"),
  },
  "./key-value": {
    KeyValue: evidence(
      "renders key-value pairs with monospace values by default and body text when requested",
      "run_display_primary",
    ),
    KeyValueList: evidence(
      "renders key-value pairs with monospace values by default and body text when requested",
      "OpenAI",
    ),
  },
  "./label": {
    Label: evidence("associates labels with inputs and exposes input state variants", "API key"),
  },
  "./select": {
    Select: evidence("selects options through the rendered select trigger and popup", "Select a model"),
    SelectContent: evidence("selects options through the rendered select trigger and popup", "data-slot='select-content'"),
    SelectGroup: evidence("selects options through the rendered select trigger and popup", "data-slot='select-group'"),
    SelectItem: evidence("selects options through the rendered select trigger and popup", "data-slot='select-item'"),
    SelectLabel: evidence("selects options through the rendered select trigger and popup", "Hosted models"),
    SelectScrollDownButton: evidence("renders public select scroll arrow exports when kept mounted", "manual-down-arrow"),
    SelectScrollUpButton: evidence("renders public select scroll arrow exports when kept mounted", "manual-up-arrow"),
    SelectSeparator: evidence("selects options through the rendered select trigger and popup", "select-separator"),
    SelectTrigger: evidence("selects options through the rendered select trigger and popup", "select-trigger"),
    SelectValue: evidence("selects options through the rendered select trigger and popup", "Select a model"),
  },
  "./segmented-control": {
    SegmentedControl: evidence(
      "marks the active segmented control option and ignores disabled option clicks",
      "aria-pressed",
    ),
  },
  "./skeleton": {
    Skeleton: evidence("renders skeleton variants as busy loading placeholders", "aria-busy"),
  },
  "./slider": {
    Slider: evidence("exposes range slider semantics and forwards value changes", "Temperature"),
  },
  "./stat-card": {
    StatCard: evidence("renders stat cards with inferred and explicit delta tones", "stat-card-delta"),
  },
  "./status-dot": {
    StatusDot: evidence("renders status dots with the requested tone and animation contract", "data-slot='status-dot'"),
  },
  "./switch": {
    Switch: evidence("toggles switches from their visible label and keeps label text rendered", "aria-checked"),
  },
  "./table": {
    Table: evidence("renders table wrappers, sortable headers, and monospace data cells", "data-slot='table-container'"),
    TableBody: evidence("renders table wrappers, sortable headers, and monospace data cells", "Completed"),
    TableCaption: evidence("renders table wrappers, sortable headers, and monospace data cells", "Recent runs"),
    TableCell: evidence("renders table wrappers, sortable headers, and monospace data cells", "1 run"),
    TableFooter: evidence("renders table wrappers, sortable headers, and monospace data cells", "tfoot"),
    TableHead: evidence("renders table wrappers, sortable headers, and monospace data cells", "aria-sort"),
    TableHeader: evidence("renders table wrappers, sortable headers, and monospace data cells", "columnheader"),
    TableMonoCell: evidence("renders table wrappers, sortable headers, and monospace data cells", "run_display_primary"),
    TableRow: evidence("renders table wrappers, sortable headers, and monospace data cells", "aria-selected"),
  },
  "./tag-input": {
    TagInput: evidence("adds, deduplicates, and removes tags through the rendered tag-input surface", "Remove alpha"),
  },
  "./tabs": {
    TabBadge: evidence("switches tabs through the rendered trigger and panel surface", "font-mono"),
    Tabs: evidence("switches tabs through the rendered trigger and panel surface", "Overview content"),
    TabsContent: evidence("switches tabs through the rendered trigger and panel surface", "Runs content"),
    TabsList: evidence("switches tabs through the rendered trigger and panel surface", "tablist"),
    TabsTrigger: evidence("switches tabs through the rendered trigger and panel surface", "aria-selected"),
  },
  "./textarea": {
    Textarea: evidence("renders textarea code and auto-resize styling contracts", "line two"),
  },
  "./tooltip": {
    SoulTip: evidence("shows tooltip content on hover and keeps the popup non-interactive", "writer_main"),
    Tooltip: evidence("shows tooltip content on hover and keeps the popup non-interactive", "Need help"),
    TooltipContent: evidence("shows tooltip content on hover and keeps the popup non-interactive", "Helpful copy"),
    TooltipProvider: evidence("shows tooltip content on hover and keeps the popup non-interactive", "Helpful copy"),
    TooltipTrigger: evidence("shows tooltip content on hover and keeps the popup non-interactive", "Need help"),
  },
};
