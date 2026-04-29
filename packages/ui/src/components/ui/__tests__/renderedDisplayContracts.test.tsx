import * as React from "react";
import { CircleAlertIcon } from "lucide-react";
import { describe, expect, it } from "vitest";

import { RunStatusDot } from "../../../../RunStatusDot";
import { render, screen } from "../../../test/testUtils";
import { EmptyState } from "../../shared/EmptyState";
import { Badge, BadgeDot } from "../badge";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../card";
import { KeyValue, KeyValueList } from "../key-value";
import { Skeleton } from "../skeleton";
import { StatCard } from "../stat-card";
import { StatusDot } from "../status-dot";

describe("rendered display contracts", () => {
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
    expect(icon?.getAttribute("aria-hidden")).toBe("true");

    rerender(<EmptyState icon={CircleAlertIcon} title="No runs yet" />);

    expect(screen.queryByRole("button", { name: "Create workflow" })).toBeNull();
    expect(container.querySelector("[data-slot='empty-state-description']")).toBeNull();
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
