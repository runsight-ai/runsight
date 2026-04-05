import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { SegmentedControl } from "../components/ui/segmented-control";

const meta: Meta<typeof SegmentedControl> = {
  title: "Navigation/Segmented Control",
  component: SegmentedControl,
  parameters: { layout: "centered" },
};

export default meta;

type Story = StoryObj<typeof SegmentedControl>;

const CanvasIcon = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2.25" y="2.25" width="11.5" height="11.5" rx="1.75" />
    <path d="M5.5 8h5" />
    <path d="M8 5.5v5" />
  </svg>
);

const CodeIcon = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 4 2.75 8 6 12" />
    <path d="m10 4 3.25 4L10 12" />
  </svg>
);

export const Default: Story = {
  name: "Default",
  render: () => {
    const [activeToggle, setActiveToggle] = React.useState("canvas");

    return (
      <SegmentedControl
        aria-label="View mode"
        activeToggle={activeToggle}
        onClick={setActiveToggle}
        options={[
          { value: "canvas", label: "Canvas" },
          { value: "yaml", label: "YAML" },
        ]}
      />
    );
  },
};

export const WithIcons: Story = {
  name: "With Icons",
  render: () => {
    const [activeToggle, setActiveToggle] = React.useState("canvas");

    return (
      <SegmentedControl
        aria-label="View mode"
        activeToggle={activeToggle}
        onClick={setActiveToggle}
        options={[
          { value: "canvas", label: "Canvas", icon: <CanvasIcon /> },
          { value: "yaml", label: "YAML", icon: <CodeIcon /> },
        ]}
      />
    );
  },
};

export const WithDisabledOption: Story = {
  name: "With Disabled Option",
  render: () => (
    <SegmentedControl
      aria-label="Surface mode"
      activeToggle="canvas"
      onClick={() => undefined}
      options={[
        { value: "canvas", label: "Canvas" },
        { value: "yaml", label: "YAML", disabled: true },
      ]}
    />
  ),
};
