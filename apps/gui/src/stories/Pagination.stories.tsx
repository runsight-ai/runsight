import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Navigation/Pagination",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <nav className="pagination" aria-label="Pagination">
      <button className="pagination__btn" aria-label="Previous page" disabled>‹</button>
      <button className="pagination__btn" aria-current="page">1</button>
      <button className="pagination__btn">2</button>
      <button className="pagination__btn">3</button>
      <span style={{ color: "var(--text-muted)", padding: "0 var(--space-1)" }}>…</span>
      <button className="pagination__btn">10</button>
      <button className="pagination__btn" aria-label="Next page">›</button>
    </nav>
  ),
};

export const MiddlePage: Story = {
  name: "Middle Page",
  render: () => (
    <nav className="pagination" aria-label="Pagination">
      <button className="pagination__btn" aria-label="Previous page">‹</button>
      <button className="pagination__btn">1</button>
      <span style={{ color: "var(--text-muted)", padding: "0 var(--space-1)" }}>…</span>
      <button className="pagination__btn">4</button>
      <button className="pagination__btn" aria-current="page">5</button>
      <button className="pagination__btn">6</button>
      <span style={{ color: "var(--text-muted)", padding: "0 var(--space-1)" }}>…</span>
      <button className="pagination__btn">10</button>
      <button className="pagination__btn" aria-label="Next page">›</button>
    </nav>
  ),
};

export const FewPages: Story = {
  name: "Few Pages (no ellipsis)",
  render: () => (
    <nav className="pagination" aria-label="Pagination">
      <button className="pagination__btn" aria-label="Previous page">‹</button>
      <button className="pagination__btn">1</button>
      <button className="pagination__btn" aria-current="page">2</button>
      <button className="pagination__btn">3</button>
      <button className="pagination__btn">4</button>
      <button className="pagination__btn">5</button>
      <button className="pagination__btn" aria-label="Next page">›</button>
    </nav>
  ),
};

export const WithInfo: Story = {
  name: "With Range Info",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
      <span className="pagination__info">1–10 of 100</span>
      <nav className="pagination" aria-label="Pagination">
        <button className="pagination__btn" aria-label="Previous page" disabled>‹</button>
        <button className="pagination__btn" aria-current="page">1</button>
        <button className="pagination__btn">2</button>
        <button className="pagination__btn">3</button>
        <span style={{ color: "var(--text-muted)", padding: "0 var(--space-1)" }}>…</span>
        <button className="pagination__btn">10</button>
        <button className="pagination__btn" aria-label="Next page">›</button>
      </nav>
    </div>
  ),
};

export const LastPage: Story = {
  name: "Last Page",
  render: () => (
    <nav className="pagination" aria-label="Pagination">
      <button className="pagination__btn" aria-label="Previous page">‹</button>
      <button className="pagination__btn">1</button>
      <span style={{ color: "var(--text-muted)", padding: "0 var(--space-1)" }}>…</span>
      <button className="pagination__btn">9</button>
      <button className="pagination__btn" aria-current="page">10</button>
      <button className="pagination__btn" aria-label="Next page" disabled>›</button>
    </nav>
  ),
};
