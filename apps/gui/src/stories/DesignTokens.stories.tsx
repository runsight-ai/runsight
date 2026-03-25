import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

// ---------------------------------------------------------------------------
// Design Token Documentation Story
//
// Renders the Runsight design system tokens visually in Storybook.
// Covers: color palette (neutral, accent, semantic), typography scale, and
// spacing scale.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Color Palette
// ---------------------------------------------------------------------------

const neutralSteps = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as const;
const accentSteps = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as const;

const semanticColors = [
  { name: "success", steps: [3, 7, 9, 11] },
  { name: "warning", steps: [3, 7, 9, 11] },
  { name: "danger", steps: [3, 7, 8, 9, 10, 11] },
  { name: "info", steps: [3, 7, 9, 11] },
] as const;

const chartColors = [1, 2, 3, 4, 5, 6, 7, 8] as const;

const blockColors = [
  "block-agent",
  "block-logic",
  "block-control",
  "block-utility",
  "block-custom",
] as const;

function Swatch({
  cssVar,
  label,
}: {
  cssVar: string;
  label: string;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: 6,
          background: `var(${cssVar})`,
          border: "1px solid rgba(255,255,255,0.1)",
        }}
      />
      <span
        style={{
          fontFamily: "var(--font-mono, monospace)",
          fontSize: 10,
          color: "var(--neutral-10, #999)",
          whiteSpace: "nowrap",
        }}
      >
        {label}
      </span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: 48 }}>
      <h2
        style={{
          fontFamily: "var(--font-display, sans-serif)",
          fontSize: "var(--font-size-xl, 18px)",
          fontWeight: 600,
          color: "var(--neutral-12, #eee)",
          marginBottom: 20,
          paddingBottom: 8,
          borderBottom: "1px solid var(--neutral-6, #333)",
        }}
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

function SwatchRow({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 16,
        marginBottom: 16,
      }}
    >
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ColorPalette Story
// ---------------------------------------------------------------------------

function ColorPaletteDoc() {
  return (
    <div style={{ padding: 32, background: "var(--neutral-1, #111)", minHeight: "100vh" }}>
      <h1
        style={{
          fontFamily: "var(--font-display, sans-serif)",
          fontSize: "var(--font-size-3xl, 24px)",
          fontWeight: 700,
          color: "var(--neutral-12, #eee)",
          marginBottom: 32,
        }}
      >
        Color Palette
      </h1>

      <Section title="Neutral Scale (12 steps)">
        <SwatchRow>
          {neutralSteps.map((step) => (
            <Swatch
              key={step}
              cssVar={`--neutral-${step}`}
              label={`neutral-${step}`}
            />
          ))}
        </SwatchRow>
      </Section>

      <Section title="Accent Scale (12 steps — amber)">
        <SwatchRow>
          {accentSteps.map((step) => (
            <Swatch
              key={step}
              cssVar={`--accent-${step}`}
              label={`accent-${step}`}
            />
          ))}
        </SwatchRow>
      </Section>

      <Section title="Semantic Hues (success, warning, danger, info)">
        {semanticColors.map(({ name, steps }) => (
          <div key={name} style={{ marginBottom: 16 }}>
            <p
              style={{
                fontFamily: "var(--font-mono, monospace)",
                fontSize: 11,
                color: "var(--neutral-10, #999)",
                marginBottom: 8,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              {name}
            </p>
            <SwatchRow>
              {steps.map((step) => (
                <Swatch
                  key={step}
                  cssVar={`--${name}-${step}`}
                  label={`${name}-${step}`}
                />
              ))}
            </SwatchRow>
          </div>
        ))}
      </Section>

      <Section title="Chart Palette (8 colors)">
        <SwatchRow>
          {chartColors.map((n) => (
            <Swatch key={n} cssVar={`--chart-${n}`} label={`chart-${n}`} />
          ))}
        </SwatchRow>
      </Section>

      <Section title="Block Category Colors">
        <SwatchRow>
          {blockColors.map((name) => (
            <Swatch key={name} cssVar={`--${name}`} label={name} />
          ))}
        </SwatchRow>
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Typography Scale Story
// ---------------------------------------------------------------------------

const fontSizeScale = [
  { token: "--font-size-2xs", label: "2xs — 11px" },
  { token: "--font-size-xs", label: "xs — 12px" },
  { token: "--font-size-sm", label: "sm — 13px" },
  { token: "--font-size-md", label: "md — 14px (base)" },
  { token: "--font-size-lg", label: "lg — 16px" },
  { token: "--font-size-xl", label: "xl — 18px" },
  { token: "--font-size-2xl", label: "2xl — 20px" },
  { token: "--font-size-3xl", label: "3xl — 24px" },
] as const;

function TypographyDoc() {
  return (
    <div style={{ padding: 32, background: "var(--neutral-1, #111)", minHeight: "100vh" }}>
      <h1
        style={{
          fontFamily: "var(--font-display, sans-serif)",
          fontSize: "var(--font-size-3xl, 24px)",
          fontWeight: 700,
          color: "var(--neutral-12, #eee)",
          marginBottom: 32,
        }}
      >
        Typography Scale
      </h1>

      <Section title="Type Scale — font-size tokens">
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {fontSizeScale.map(({ token, label }) => (
            <div
              key={token}
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 24,
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-mono, monospace)",
                  fontSize: 11,
                  color: "var(--neutral-9, #888)",
                  width: 160,
                  flexShrink: 0,
                }}
              >
                {label}
              </span>
              <span
                style={{
                  fontFamily: "var(--font-body, sans-serif)",
                  fontSize: `var(${token})`,
                  color: "var(--neutral-12, #eee)",
                }}
              >
                The quick brown fox jumps over the lazy dog
              </span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Font Families">
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div>
            <p
              style={{
                fontFamily: "var(--font-mono, monospace)",
                fontSize: 11,
                color: "var(--accent-9, #f5a623)",
                marginBottom: 8,
              }}
            >
              --font-display: Satoshi — headlines &amp; display
            </p>
            <p
              style={{
                fontFamily: "var(--font-display, 'Satoshi', sans-serif)",
                fontSize: "var(--font-size-2xl, 20px)",
                fontWeight: 700,
                color: "var(--neutral-12, #eee)",
              }}
            >
              Build AI agents that think, act, and adapt.
            </p>
          </div>
          <div>
            <p
              style={{
                fontFamily: "var(--font-mono, monospace)",
                fontSize: 11,
                color: "var(--accent-9, #f5a623)",
                marginBottom: 8,
              }}
            >
              --font-body: Geist — primary UI text
            </p>
            <p
              style={{
                fontFamily: "var(--font-body, 'Geist', sans-serif)",
                fontSize: "var(--font-size-md, 14px)",
                color: "var(--neutral-11, #ccc)",
              }}
            >
              Runsight is a meta-framework for AI agent orchestration. Design,
              run, and observe your workflows in a unified visual environment.
            </p>
          </div>
          <div>
            <p
              style={{
                fontFamily: "var(--font-mono, monospace)",
                fontSize: 11,
                color: "var(--accent-9, #f5a623)",
                marginBottom: 8,
              }}
            >
              --font-mono: JetBrains Mono — code, data, metrics
            </p>
            <p
              style={{
                fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                fontSize: "var(--font-size-sm, 13px)",
                color: "var(--neutral-11, #ccc)",
              }}
            >
              {`steps:\n  - id: run_agent\n    soul: gpt-4o-researcher`}
            </p>
          </div>
        </div>
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Spacing Scale Story
// ---------------------------------------------------------------------------

const spacingScale = [
  { token: "--space-1", px: 4 },
  { token: "--space-2", px: 8 },
  { token: "--space-3", px: 12 },
  { token: "--space-4", px: 16 },
  { token: "--space-5", px: 20 },
  { token: "--space-6", px: 24 },
  { token: "--space-8", px: 32 },
  { token: "--space-10", px: 40 },
  { token: "--space-12", px: 48 },
] as const;

function SpacingDoc() {
  return (
    <div style={{ padding: 32, background: "var(--neutral-1, #111)", minHeight: "100vh" }}>
      <h1
        style={{
          fontFamily: "var(--font-display, sans-serif)",
          fontSize: "var(--font-size-3xl, 24px)",
          fontWeight: 700,
          color: "var(--neutral-12, #eee)",
          marginBottom: 32,
        }}
      >
        Spacing Scale
      </h1>

      <Section title="Space tokens — gap, padding, margin">
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {spacingScale.map(({ token, px }) => (
            <div
              key={token}
              style={{ display: "flex", alignItems: "center", gap: 24 }}
            >
              <span
                style={{
                  fontFamily: "var(--font-mono, monospace)",
                  fontSize: 11,
                  color: "var(--neutral-9, #888)",
                  width: 160,
                  flexShrink: 0,
                }}
              >
                {token} ({px}px)
              </span>
              <div
                style={{
                  height: 20,
                  width: `var(${token})`,
                  background: "var(--accent-9, #f5a623)",
                  borderRadius: 2,
                  minWidth: 2,
                }}
              />
            </div>
          ))}
        </div>
      </Section>

      <Section title="Density Contexts">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[
            { token: "--gap-condensed", label: "gap-condensed (8px)" },
            { token: "--gap-normal", label: "gap-normal (16px)" },
            { token: "--gap-spacious", label: "gap-spacious (24px)" },
            { token: "--padding-condensed", label: "padding-condensed (8px)" },
            { token: "--padding-normal", label: "padding-normal (16px)" },
            { token: "--padding-spacious", label: "padding-spacious (24px)" },
          ].map(({ token, label }) => (
            <div
              key={token}
              style={{ display: "flex", alignItems: "center", gap: 24 }}
            >
              <span
                style={{
                  fontFamily: "var(--font-mono, monospace)",
                  fontSize: 11,
                  color: "var(--neutral-9, #888)",
                  width: 260,
                  flexShrink: 0,
                }}
              >
                {label}
              </span>
              <div
                style={{
                  height: 20,
                  width: `var(${token})`,
                  background: "var(--accent-7, #b47e20)",
                  borderRadius: 2,
                  minWidth: 2,
                }}
              />
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Storybook Meta
// ---------------------------------------------------------------------------

const meta: Meta = {
  title: "Design System / Design Tokens",
};

export default meta;

type Story = StoryObj;

export const ColorPalette: Story = {
  render: () => <ColorPaletteDoc />,
  name: "Color Palette",
};

export const TypographyScale: Story = {
  render: () => <TypographyDoc />,
  name: "Typography Scale",
};

export const SpacingScale: Story = {
  render: () => <SpacingDoc />,
  name: "Spacing Scale",
};
