import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Composites/NodeCard",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

const AgentIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
  </svg>
);

const LogicIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
  </svg>
);

const UtilityIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 004.486-6.336l-3.276 3.277a3.004 3.004 0 01-2.25-2.25l3.276-3.276a4.5 4.5 0 00-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437l1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008z" />
  </svg>
);

export const Default: Story = {
  render: () => (
    <div className="node-card" data-category="agent">
      <div className="node-card__header">
        <div className="node-card__icon"><AgentIcon /></div>
        <div className="node-card__name">Research Agent</div>
      </div>
      <div className="node-card__meta">
        <span>AGENT</span>
        <span className="node-card__meta-sep">·</span>
        <span>GPT-4</span>
      </div>
      <span className="node-card__cost-badge">$0.0012</span>
      <div className="node-card__port node-card__port--input" />
      <div className="node-card__port node-card__port--output" />
    </div>
  ),
};

export const CategoryAgent: Story = {
  name: "Category — agent",
  render: () => (
    <div className="node-card" data-category="agent">
      <div className="node-card__header">
        <div className="node-card__icon"><AgentIcon /></div>
        <div className="node-card__name">Research Agent</div>
      </div>
      <div className="node-card__meta"><span>AGENT</span></div>
      <span className="node-card__cost-badge">$0.0024</span>
    </div>
  ),
};

export const CategoryLogic: Story = {
  name: "Category — logic",
  render: () => (
    <div className="node-card" data-category="logic">
      <div className="node-card__header">
        <div className="node-card__icon"><LogicIcon /></div>
        <div className="node-card__name">Route Decision</div>
      </div>
      <div className="node-card__meta"><span>LOGIC</span></div>
    </div>
  ),
};

export const CategoryControl: Story = {
  name: "Category — control",
  render: () => (
    <div className="node-card" data-category="control">
      <div className="node-card__header">
        <div className="node-card__icon"><UtilityIcon /></div>
        <div className="node-card__name">Loop Until</div>
      </div>
      <div className="node-card__meta"><span>CONTROL</span></div>
    </div>
  ),
};

export const CategoryUtility: Story = {
  name: "Category — utility",
  render: () => (
    <div className="node-card" data-category="utility">
      <div className="node-card__header">
        <div className="node-card__icon"><UtilityIcon /></div>
        <div className="node-card__name">Format Output</div>
      </div>
      <div className="node-card__meta"><span>UTILITY</span></div>
    </div>
  ),
};

export const StateRunning: Story = {
  name: "Execution state — running",
  render: () => (
    <div className="node-card" data-category="agent" data-state="running">
      <div className="node-card__header">
        <div className="node-card__icon"><AgentIcon /></div>
        <div className="node-card__name">Summarise Results</div>
      </div>
      <div className="node-card__meta"><span>AGENT</span></div>
      <span className="node-card__cost-badge">$0.0008</span>
    </div>
  ),
};

export const StateCompleted: Story = {
  name: "Execution state — completed",
  render: () => (
    <div className="node-card" data-category="utility" data-state="completed">
      <div className="node-card__header">
        <div className="node-card__icon"><UtilityIcon /></div>
        <div className="node-card__name">Fetch Data</div>
      </div>
      <div className="node-card__meta"><span>UTILITY</span></div>
      <span className="node-card__cost-badge">$0.0003</span>
    </div>
  ),
};

export const StateFailed: Story = {
  name: "Execution state — failed",
  render: () => (
    <div className="node-card" data-category="logic" data-state="failed">
      <div className="node-card__header">
        <div className="node-card__icon"><LogicIcon /></div>
        <div className="node-card__name">Validate Schema</div>
      </div>
      <div className="node-card__meta"><span>LOGIC</span></div>
    </div>
  ),
};

export const Selected: Story = {
  name: "Selected state",
  render: () => (
    <div className="node-card" data-category="agent" aria-selected="true">
      <div className="node-card__header">
        <div className="node-card__icon"><AgentIcon /></div>
        <div className="node-card__name">Research Agent</div>
      </div>
      <div className="node-card__meta"><span>AGENT</span></div>
      <span className="node-card__cost-badge">$0.0012</span>
    </div>
  ),
};

export const AllCategories: Story = {
  name: "All block categories",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", width: "260px" }}>
      <div className="node-card" data-category="agent">
        <div className="node-card__header">
          <div className="node-card__icon"><AgentIcon /></div>
          <div className="node-card__name">Research Agent</div>
        </div>
        <div className="node-card__meta"><span>AGENT</span></div>
        <span className="node-card__cost-badge">$0.0024</span>
      </div>
      <div className="node-card" data-category="logic">
        <div className="node-card__header">
          <div className="node-card__icon"><LogicIcon /></div>
          <div className="node-card__name">Route Decision</div>
        </div>
        <div className="node-card__meta"><span>LOGIC</span></div>
      </div>
      <div className="node-card" data-category="control">
        <div className="node-card__header">
          <div className="node-card__icon"><UtilityIcon /></div>
          <div className="node-card__name">Loop Until</div>
        </div>
        <div className="node-card__meta"><span>CONTROL</span></div>
      </div>
      <div className="node-card" data-category="utility">
        <div className="node-card__header">
          <div className="node-card__icon"><UtilityIcon /></div>
          <div className="node-card__name">Format Output</div>
        </div>
        <div className="node-card__meta"><span>UTILITY</span></div>
      </div>
      <div className="node-card" data-category="custom">
        <div className="node-card__header">
          <div className="node-card__icon"><AgentIcon /></div>
          <div className="node-card__name">My Custom Block</div>
        </div>
        <div className="node-card__meta"><span>CUSTOM</span></div>
      </div>
    </div>
  ),
};

export const AllExecutionStates: Story = {
  name: "All execution states",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", width: "260px" }}>
      {(["idle", "running", "completed", "failed"] as const).map((state) => (
        <div key={state} className="node-card" data-category="agent" data-state={state === "idle" ? undefined : state}>
          <div className="node-card__header">
            <div className="node-card__icon"><AgentIcon /></div>
            <div className="node-card__name">{state.charAt(0).toUpperCase() + state.slice(1)}</div>
          </div>
          <div className="node-card__meta"><span>AGENT</span></div>
        </div>
      ))}
    </div>
  ),
};
