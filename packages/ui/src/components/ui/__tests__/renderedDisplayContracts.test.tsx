import * as React from "react";
import { CircleAlertIcon } from "lucide-react";
import { describe, expect, it } from "vitest";

import { RunStatusDot } from "../../../../RunStatusDot";
import { render, screen } from "../../../test/testUtils";
import { EmptyState } from "../../shared/EmptyState";
import { Avatar, AvatarGroup } from "../avatar";
import { Badge, BadgeDot } from "../badge";
import {
  Breadcrumb,
  BreadcrumbEllipsis,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "../breadcrumb";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../card";
import { Divider } from "../divider";
import { Field, FieldError, FieldHelper, FieldLabel } from "../field";
import { Icon } from "../icon";
import { KeyValue, KeyValueList } from "../key-value";
import { Link } from "../link";
import { NodeCard } from "../node-card";
import { Progress } from "../progress";
import { Skeleton } from "../skeleton";
import { Spinner } from "../spinner";
import { StatCard } from "../stat-card";
import { StatusDot } from "../status-dot";

describe("rendered display contracts", () => {
  it("renders avatar initials, images, and stacked group presentation", () => {
    const { container, rerender } = render(
      <AvatarGroup aria-label="Assigned souls">
        <Avatar size="lg">AD</Avatar>
        <Avatar size="sm">QA</Avatar>
      </AvatarGroup>,
    );

    const group = container.querySelector("[data-slot='avatar-group']");
    const avatars = container.querySelectorAll("[data-slot='avatar']");

    expect(group?.className).toContain("flex-row-reverse");
    expect(avatars).toHaveLength(2);
    expect(avatars[0]?.className).toContain("w-10");
    expect(avatars[0]?.className).toContain("ml-0");
    expect(avatars[1]?.className).toContain("w-6");
    expect(avatars[1]?.className).toContain("-ml-2");

    rerender(<Avatar src="/avatar.png" alt="Ada Lovelace" />);

    const image = screen.getByAltText("Ada Lovelace");
    expect(image.tagName).toBe("IMG");
    expect(image.className).toContain("object-cover");
  });

  it("renders link, icon, divider, and field composition contracts", () => {
    const { container } = render(
      <Field>
        <FieldLabel htmlFor="workflow-name" required>
          Workflow name
        </FieldLabel>
        <Link href="https://example.test" variant="external">
          Docs
        </Link>
        <Icon size="xl" aria-hidden="true">
          <CircleAlertIcon />
        </Icon>
        <Divider orientation="vertical" />
        <FieldHelper>Visible to teammates.</FieldHelper>
        <FieldError>Required</FieldError>
      </Field>,
    );

    const field = container.querySelector("[data-slot='field']");
    const link = screen.getByRole("link", { name: /Docs/ });
    const icon = container.querySelector("[data-slot='icon']");
    const divider = screen.getByRole("separator");

    expect(field?.className).toContain("flex");
    expect(field?.className).toContain("gap-1");
    expect(screen.getByText("Workflow name").textContent).toContain("*");
    expect(link.className).toContain("text-accent");
    expect(link.textContent).toContain("↗");
    expect(icon?.className).toContain("size-6");
    expect(divider.getAttribute("aria-orientation")).toBe("vertical");
    expect(divider.className).toContain("w-px");
    expect(screen.getByText("Visible to teammates.").className).toContain("text-muted");
    expect(screen.getByText("Required").className).toContain("text-danger-11");
  });

  it("renders breadcrumb, progress, and spinner presentation contracts", () => {
    const { container, rerender } = render(
      <div>
        <Breadcrumb separator="/">
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink href="/runs">Runs</BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbEllipsis />
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage variant="id">RUN-423</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <Progress value={140} variant="success" />
        <Spinner size="lg" variant="accent" />
      </div>,
    );

    const breadcrumb = screen.getByRole("navigation", { name: "breadcrumb" });
    const currentPage = screen.getByText("RUN-423");
    const separators = container.querySelectorAll("[role='presentation'][aria-hidden='true']");
    const progress = screen.getByRole("progressbar");
    const spinner = screen.getByRole("status", { name: "Loading" });

    expect(breadcrumb.className).toContain("overflow-hidden");
    expect(screen.getByRole("link", { name: "Runs" }).className).toContain("text-muted");
    expect(currentPage.getAttribute("aria-current")).toBe("page");
    expect(currentPage.className).toContain("font-mono");
    expect(separators[0]?.textContent).toBe("/");
    expect(progress.getAttribute("aria-valuenow")).toBe("100");
    expect(container.querySelector("[data-slot='progress-fill']")?.getAttribute("style")).toContain("width: 100%");
    expect(spinner.className).toContain("text-interactive-default");
    expect(spinner.querySelector("span")?.className).toContain("w-[24px]");

    rerender(<Progress variant="indeterminate" value={50} />);

    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBeNull();
    expect(container.querySelector("[data-slot='progress-fill']")?.className).toContain("progress-slide");
  });

  it("renders badge variants and the decorative badge dot", () => {
    render(
      <Badge variant="warning">
        <BadgeDot />
        Needs review
      </Badge>,
    );

    const badge = screen.getByText("Needs review");
    const dot = badge.parentElement?.querySelector("[data-slot='badge-dot']");

    expect(badge.className).toContain("bg-warning-3");
    expect(badge.className).toContain("text-warning-11");
    expect(dot).not.toBeNull();
  });

  it("renders status dots with the requested tone and animation contract", () => {
    const { rerender, container } = render(<StatusDot variant="danger" animate="spin" />);

    let dot = container.querySelector("[data-slot='status-dot']");
    expect(dot).not.toBeNull();
    expect(dot?.className).toContain("animate-spin");
    expect(dot?.className).toContain("border-2");
    expect(dot?.className).toContain("border-current");
    expect(dot?.className).toContain("bg-transparent");

    rerender(<StatusDot variant="success" animate="none" />);

    dot = container.querySelector("[data-slot='status-dot']");
    expect(dot?.className).toContain("bg-success");
    expect(dot?.className.includes("animate-spin")).toBe(false);
  });

  it("maps runtime run statuses onto observable status-dot presentation", () => {
    const { rerender, container } = render(<RunStatusDot status="running" className="ml-2" />);

    const wrapper = container.querySelector("span[title='running']");
    let dot = container.querySelector("[data-slot='status-dot']");

    expect(wrapper?.className).toContain("inline-flex");
    expect(wrapper?.className).toContain("ml-2");
    expect(screen.getByText("running").className).toBe("sr-only");
    expect(dot?.className).toContain("bg-warning");
    expect(dot?.className).toContain("animate-pulse");

    rerender(<RunStatusDot status="PAUSED" />);
    dot = container.querySelector("[data-slot='status-dot']");
    expect(dot?.className).toContain("bg-info-9");

    rerender(<RunStatusDot status="mystery" />);
    dot = container.querySelector("[data-slot='status-dot']");
    expect(dot?.className).toContain("bg-neutral-9");
  });

  it("renders empty states with optional description and action affordances", () => {
    const onClick = () => undefined;
    const { rerender, container } = render(
      <EmptyState
        icon={CircleAlertIcon}
        title="No runs yet"
        description="Create a workflow to start collecting data."
        action={{ label: "Create workflow", onClick }}
      />,
    );

    expect(screen.getByText("No runs yet").tagName).toBe("H2");
    expect(screen.getByText("Create a workflow to start collecting data.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Create workflow" })).toBeTruthy();

    const iconContainer = container.querySelector("[data-slot='empty-state-icon']");
    const icon = iconContainer?.querySelector("svg");
    const title = screen.getByText("No runs yet");
    const description = screen.getByText("Create a workflow to start collecting data.");

    expect(icon?.getAttribute("aria-hidden")).toBe("true");
    expect(iconContainer?.className).toContain("text-(--text-muted)");
    expect(iconContainer?.className).toContain("w-12");
    expect(title.className).toContain("text-[length:var(--font-size-lg)]");
    expect(title.className).toContain("text-(--text-primary)");
    expect(description.className).toContain("text-[length:var(--font-size-sm)]");
    expect(description.className).toContain("text-(--text-secondary)");

    rerender(<EmptyState icon={CircleAlertIcon} title="No runs yet" />);

    expect(screen.queryByRole("button", { name: "Create workflow" })).toBeNull();
    expect(container.querySelector("[data-slot='empty-state-description']")).toBeNull();
  });

  it("renders node cards with category, execution, selected, port, and cost contracts", () => {
    const { container, rerender } = render(
      <NodeCard
        title="Research Agent"
        category="block-agent"
        executionState="running"
        selected
        cost="$0.0024"
        icon={<CircleAlertIcon />}
        inputPort
        outputPort
        meta={["Linear", "2 ports"]}
        ports={[
          { name: "pass", type: "pass" },
          { name: "fail", type: "fail" },
        ]}
      />,
    );

    let card = container.querySelector("[data-slot='node-card']");
    const title = container.querySelector("[data-slot='node-card-title']");
    const cost = container.querySelector("[data-slot='node-card-cost']");
    const ports = container.querySelectorAll("[data-slot='node-card-port']");

    expect(card?.getAttribute("data-category")).toBe("block-agent");
    expect(card?.getAttribute("data-state")).toBe("running");
    expect(card?.getAttribute("aria-selected")).toBe("true");
    expect(card?.className).toContain("bg-(--surface-tertiary)");
    expect(card?.className).toContain("border-t-[var(--accent-9)]");
    expect(card?.className).toContain("border-l-accent-9/50");
    expect(title?.className).toContain("text-(--text-heading)");
    expect(cost?.textContent).toBe("$0.0024");
    expect(cost?.className).toContain("font-mono");
    expect(ports).toHaveLength(2);
    expect(screen.getByText("pass").className).toContain("font-mono");

    rerender(
      <NodeCard
        title="Route Decision"
        category="block-logic"
        executionState="success"
        icon={<CircleAlertIcon />}
      />,
    );

    card = container.querySelector("[data-slot='node-card']");
    expect(card?.getAttribute("data-category")).toBe("block-logic");
    expect(card?.className).toContain("border-t-[var(--success-9)]");
  });

  it("renders card composition slots and raised interactive styling", () => {
    const { container } = render(
      <Card raised interactive>
        <CardHeader>
          <CardTitle>Workflow health</CardTitle>
          <CardAction>Actions</CardAction>
        </CardHeader>
        <CardContent>
          <CardDescription>Everything looks healthy.</CardDescription>
        </CardContent>
        <CardFooter>Updated just now</CardFooter>
      </Card>,
    );

    const card = container.querySelector("[data-slot='card']");
    expect(card?.className).toContain("bg-surface-raised");
    expect(card?.className).toContain("shadow-raised");
    expect(card?.className).toContain("cursor-pointer");
    expect(container.querySelector("[data-slot='card-header']")).not.toBeNull();
    expect(container.querySelector("[data-slot='card-content']")).not.toBeNull();
    expect(container.querySelector("[data-slot='card-footer']")).not.toBeNull();
    expect(screen.getByText("Workflow health").className).toContain("text-heading");
  });

  it("renders skeleton variants as busy loading placeholders", () => {
    const { rerender, container } = render(<Skeleton variant="avatar" />);

    let skeleton = container.querySelector("[data-slot='skeleton']");
    expect(skeleton?.getAttribute("aria-busy")).toBe("true");
    expect(skeleton?.getAttribute("aria-label")).toBe("Loading");
    expect(skeleton?.className).toContain("rounded-full");
    expect(skeleton?.className).toContain("w-8");

    rerender(<Skeleton variant="button" />);
    skeleton = container.querySelector("[data-slot='skeleton']");
    expect(skeleton?.className).toContain("h-8");
    expect(skeleton?.className).toContain("w-[100px]");
  });

  it("renders stat cards with inferred and explicit delta tones", () => {
    const { rerender, container } = render(
      <StatCard label="success rate" value="98%" delta="+4%" icon={<CircleAlertIcon />} />,
    );

    let delta = container.querySelector("[data-slot='stat-card-delta']");
    expect(screen.getByText("success rate").className).toContain("uppercase");
    expect(screen.getByText("98%").className).toContain("text-3xl");
    expect(container.querySelector("[data-slot='stat-card-icon']")).not.toBeNull();
    expect(delta?.className).toContain("text-success-11");

    rerender(<StatCard label="errors" value="12" delta="flat" deltaTone="negative" />);
    delta = container.querySelector("[data-slot='stat-card-delta']");
    expect(delta?.className).toContain("text-danger-11");
  });

  it("renders key-value pairs with monospace values by default and body text when requested", () => {
    const { rerender } = render(<KeyValue label="Run ID" value="run_display_primary" />);

    const monoValue = screen.getByText("run_display_primary");
    expect(monoValue.className).toContain("font-mono");

    rerender(
      <KeyValueList
        items={[
          { label: "Model", value: "gpt-5.4", mono: false },
          { label: "Provider", value: "OpenAI" },
        ]}
      />,
    );

    expect(screen.getByText("Model")).toBeTruthy();
    expect(screen.getByText("gpt-5.4").className).toContain("font-[var(--font-body)]");
    expect(screen.getByText("OpenAI").className).toContain("font-mono");
  });
});
