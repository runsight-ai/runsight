import * as React from "react";
import { describe, expect, it, vi } from "vitest";

import { createUser, fireEvent, render, screen, waitFor } from "../../../test/testUtils";
import { Button } from "../button";
import { Input } from "../input";
import { Label } from "../label";
import { SegmentedControl } from "../segmented-control";
import { Slider } from "../slider";
import { Switch } from "../switch";
import { TagInput } from "../tag-input";
import { Textarea } from "../textarea";

function SwitchHarness(props: React.ComponentProps<typeof Switch>) {
  const [checked, setChecked] = React.useState(false);

  return <Switch {...props} checked={checked} onCheckedChange={setChecked} />;
}

function TagInputHarness(props: Omit<React.ComponentProps<typeof TagInput>, "tags" | "onChange">) {
  const [tags, setTags] = React.useState<string[]>([]);

  return <TagInput {...props} tags={tags} onChange={setTags} />;
}

describe("rendered form control contracts", () => {
  it("disables buttons and exposes a spinner when loading", () => {
    const { rerender } = render(
      <Button variant="primary" size="md" loading>
        Save workflow
      </Button>,
    );

    const loadingButton = screen.getByRole("button", { name: "Save workflow" });
    const spinner = loadingButton.querySelector("span[aria-hidden='true']");

    expect((loadingButton as HTMLButtonElement).disabled).toBe(true);
    expect(loadingButton.getAttribute("aria-busy")).toBe("true");
    expect(loadingButton.className).toContain("text-transparent");
    expect(spinner?.className).toContain("animate-spin");

    rerender(
      <Button variant="icon-only" size="md" aria-label="Open options">
        O
      </Button>,
    );

    const iconOnlyButton = screen.getByRole("button", { name: "Open options" });
    expect(iconOnlyButton.className).toContain("aspect-square");
    expect(iconOnlyButton.className).toContain("h-10");
    expect(iconOnlyButton.className).toContain("w-10");
  });

  it("associates labels with inputs and exposes input state variants", () => {
    render(
      <div>
        <Label htmlFor="api-key" required>
          API key
        </Label>
        <Input id="api-key" defaultValue="secret" error size="lg" />
      </div>,
    );

    const input = screen.getByRole("textbox") as HTMLInputElement;
    const label = screen.getByText("API key").closest("label");

    expect(input.value).toBe("secret");
    expect(input.id).toBe("api-key");
    expect(input.className).toContain("border-danger-9");
    expect(input.className).toContain("h-[var(--control-height-lg)]");
    expect(label?.getAttribute("for")).toBe("api-key");
    expect(label?.textContent).toContain("*");
  });

  it("renders textarea code and auto-resize styling contracts", () => {
    render(
      <Textarea
        aria-label="Prompt"
        code
        autoResize
        defaultValue={"line one\nline two"}
      />,
    );

    const textarea = screen.getByLabelText("Prompt") as HTMLTextAreaElement;

    expect(textarea.value).toContain("line two");
    expect(textarea.className).toContain("font-mono");
    expect(textarea.className).toContain("[tab-size:2]");
    expect(textarea.className).toContain("resize-none");
    expect(textarea.className).toContain("overflow-hidden");
  });

  it("marks the active segmented control option and ignores disabled option clicks", async () => {
    const user = createUser();
    const onClick = vi.fn();

    render(
      <SegmentedControl
        activeToggle="canvas"
        onClick={onClick}
        options={[
          { value: "canvas", label: "Canvas" },
          { value: "yaml", label: "YAML" },
          { value: "history", label: "History", disabled: true },
        ]}
      />,
    );

    const canvas = screen.getByRole("button", { name: "Canvas" });
    const yaml = screen.getByRole("button", { name: "YAML" });
    const history = screen.getByRole("button", { name: "History" });

    expect(canvas.getAttribute("aria-pressed")).toBe("true");
    expect(canvas.getAttribute("data-state")).toBe("active");
    expect(yaml.getAttribute("aria-pressed")).toBe("false");
    expect((history as HTMLButtonElement).disabled).toBe(true);

    await user.click(yaml);
    await user.click(history);

    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onClick).toHaveBeenCalledWith("yaml");
  });

  it("toggles switches from their visible label and keeps label text rendered", async () => {
    const user = createUser();

    render(<SwitchHarness label="Enabled" />);

    const switchControl = screen.getByRole("switch");
    expect(switchControl.getAttribute("aria-checked")).toBe("false");
    expect(screen.getByText("Enabled")).toBeTruthy();

    await user.click(screen.getByText("Enabled"));

    await waitFor(() => {
      expect(switchControl.getAttribute("aria-checked")).toBe("true");
    });
  });

  it("exposes range slider semantics and forwards value changes", () => {
    const onChange = vi.fn();

    render(
      <Slider
        aria-label="Temperature"
        min={10}
        max={90}
        step={5}
        defaultValue={25}
        onChange={onChange}
      />,
    );

    const slider = screen.getByRole("slider") as HTMLInputElement;

    expect(slider.min).toBe("10");
    expect(slider.max).toBe("90");
    expect(slider.step).toBe("5");
    expect(slider.value).toBe("25");
    expect(slider.className).toContain("bg-neutral-5");

    fireEvent.change(slider, { target: { value: "45" } });

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(slider.value).toBe("45");
  });

  it("associates the visible tag label with the textbox", () => {
    render(<TagInputHarness label="Tags" placeholder="Add a tag" />);

    expect(screen.getByLabelText("Tags")).toBeTruthy();
  });

  it("adds, deduplicates, and removes tags through the rendered tag-input surface", async () => {
    const user = createUser();

    render(<TagInputHarness label="Tags" placeholder="Add a tag" />);

    const input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input.placeholder).toBe("Add a tag");

    await user.type(input, " alpha ");
    await user.keyboard("{Enter}");

    expect(screen.getByText("alpha")).toBeTruthy();
    expect(input.value).toBe("");
    expect(input.placeholder).toBe("");

    await user.type(input, "alpha,");
    expect(screen.getAllByText("alpha")).toHaveLength(1);

    await user.type(input, "beta,");
    expect(screen.getByText("beta")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Remove alpha" }));
    expect(screen.queryByText("alpha")).toBeNull();

    await user.click(input);
    await user.keyboard("{Backspace}");
    expect(screen.queryByText("beta")).toBeNull();
    expect(input.placeholder).toBe("Add a tag");
  });
});
