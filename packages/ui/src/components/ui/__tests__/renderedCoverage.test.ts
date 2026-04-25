import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import * as RunStatusDotModule from "../../../../RunStatusDot";
import * as EmptyStateModule from "../../shared/EmptyState";
import * as BadgeModule from "../badge";
import * as ButtonModule from "../button";
import * as CardModule from "../card";
import * as DialogModule from "../dialog";
import * as DropdownMenuModule from "../dropdown-menu";
import * as InputModule from "../input";
import * as KeyValueModule from "../key-value";
import * as LabelModule from "../label";
import * as SelectModule from "../select";
import * as SegmentedControlModule from "../segmented-control";
import * as SkeletonModule from "../skeleton";
import * as SliderModule from "../slider";
import * as StatCardModule from "../stat-card";
import * as StatusDotModule from "../status-dot";
import * as SwitchModule from "../switch";
import * as TableModule from "../table";
import * as TabsModule from "../tabs";
import * as TagInputModule from "../tag-input";
import * as TextareaModule from "../textarea";
import * as TooltipModule from "../tooltip";

const PACKAGE_JSON_PATH = resolve(__dirname, "..", "..", "..", "..", "package.json");

const nonComponentExports = new Set(["./styles.css", "./runTable.styles", "./utils"]);

const canonicalSuites = [
  "renderedDisplayContracts.test.tsx",
  "renderedFormControls.test.tsx",
  "renderedNavigationAndOverlays.test.tsx",
] as const;

type CanonicalSuite = (typeof canonicalSuites)[number];

const renderedBaselineCoverage = {
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

type CoveredSubpath = keyof typeof renderedBaselineCoverage;

const componentModules = {
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

const nonComponentNamedExports = {
  "./badge": ["badgeVariants"],
  "./button": ["buttonVariants"],
} satisfies Partial<Record<CoveredSubpath, readonly string[]>>;

function readRetainedComponentExports() {
  const packageJson = JSON.parse(readFileSync(PACKAGE_JSON_PATH, "utf8")) as {
    exports?: Record<string, unknown>;
  };

  return Object.keys(packageJson.exports ?? {})
    .filter((subpath) => !nonComponentExports.has(subpath))
    .sort();
}

function readRuntimeComponentNames(subpath: CoveredSubpath) {
  const ignoredExports = new Set(nonComponentNamedExports[subpath] ?? []);

  return Object.keys(componentModules[subpath])
    .filter((exportName) => !ignoredExports.has(exportName))
    .sort();
}

describe("RUN-977 rendered component coverage structure", () => {
  it("assigns every retained component export to a rendered baseline suite", () => {
    expect(Object.keys(renderedBaselineCoverage).sort()).toEqual(readRetainedComponentExports());
  });

  it("lists every public named component export inside its baseline assignment", () => {
    const uncoveredComponents = Object.entries(renderedBaselineCoverage).flatMap(
      ([subpath, assignment]) => {
        const coveredComponents = new Set(assignment.components);

        return readRuntimeComponentNames(subpath as CoveredSubpath)
          .filter((componentName) => !coveredComponents.has(componentName))
          .map((componentName) => `${subpath} -> ${componentName}`);
      },
    );
    const staleComponents = Object.entries(renderedBaselineCoverage).flatMap(
      ([subpath, assignment]) => {
        const runtimeComponents = new Set(readRuntimeComponentNames(subpath as CoveredSubpath));

        return assignment.components
          .filter((componentName) => !runtimeComponents.has(componentName))
          .map((componentName) => `${subpath} -> ${componentName}`);
      },
    );

    expect(uncoveredComponents).toEqual([]);
    expect(staleComponents).toEqual([]);
  });

  it("keeps rendered component coverage grouped by the canonical baseline suites", () => {
    const canonicalSuiteSet = new Set(canonicalSuites);

    const nonCanonicalAssignments = Object.entries(renderedBaselineCoverage)
      .filter(([, assignment]) => !canonicalSuiteSet.has(assignment.suite))
      .map(([subpath, assignment]) => `${subpath} -> ${assignment.suite}`);

    expect(nonCanonicalAssignments).toEqual([]);
  });
});
