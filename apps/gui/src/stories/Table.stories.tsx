import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Data Display/Table",
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <table className="table">
      <thead className="table__head">
        <tr>
          <th className="table__header">Workflow</th>
          <th className="table__header">Status</th>
          <th className="table__header">Started</th>
          <th className="table__header">Duration</th>
        </tr>
      </thead>
      <tbody className="table__body">
        <tr className="table__row">
          <td className="table__cell">customer-support-triage</td>
          <td className="table__cell">
            <span className="badge badge--success"><span className="badge__dot" />Running</span>
          </td>
          <td className="table__cell">2 min ago</td>
          <td className="table__cell table__cell--mono">34s</td>
        </tr>
        <tr className="table__row">
          <td className="table__cell">email-classifier</td>
          <td className="table__cell">
            <span className="badge badge--neutral">Completed</span>
          </td>
          <td className="table__cell">5 min ago</td>
          <td className="table__cell table__cell--mono">12s</td>
        </tr>
        <tr className="table__row">
          <td className="table__cell">data-pipeline</td>
          <td className="table__cell">
            <span className="badge badge--danger">Failed</span>
          </td>
          <td className="table__cell">10 min ago</td>
          <td className="table__cell table__cell--mono">1m 22s</td>
        </tr>
      </tbody>
    </table>
  ),
};

export const WithMonoCells: Story = {
  name: "Mono Values",
  render: () => (
    <table className="table">
      <thead className="table__head">
        <tr>
          <th className="table__header">Workflow</th>
          <th className="table__header">Run ID</th>
          <th className="table__header">Started</th>
          <th className="table__header">Tokens</th>
        </tr>
      </thead>
      <tbody className="table__body">
        <tr className="table__row">
          <td className="table__cell">customer-support-triage</td>
          <td className="table__cell table__cell--mono" data-type="id">run_8f3k2m</td>
          <td className="table__cell table__cell--mono" data-type="timestamp">2026-03-25 09:14:00</td>
          <td className="table__cell table__cell--mono" data-type="metric">4,820</td>
        </tr>
        <tr className="table__row">
          <td className="table__cell">email-classifier</td>
          <td className="table__cell table__cell--mono" data-type="id">run_9x1p4q</td>
          <td className="table__cell table__cell--mono" data-type="timestamp">2026-03-25 09:09:00</td>
          <td className="table__cell table__cell--mono" data-type="metric">1,204</td>
        </tr>
      </tbody>
    </table>
  ),
};

export const SortableHeader: Story = {
  name: "Sortable Header",
  render: () => (
    <table className="table">
      <thead className="table__head">
        <tr>
          <th className="table__header" aria-sort="none">Workflow ↕</th>
          <th className="table__header" aria-sort="descending">Started ↓</th>
          <th className="table__header" aria-sort="none">Duration ↕</th>
          <th className="table__header">Status</th>
        </tr>
      </thead>
      <tbody className="table__body">
        <tr className="table__row">
          <td className="table__cell">customer-support-triage</td>
          <td className="table__cell table__cell--mono">2026-03-25 09:14:00</td>
          <td className="table__cell table__cell--mono">34s</td>
          <td className="table__cell"><span className="badge badge--success"><span className="badge__dot" />Running</span></td>
        </tr>
        <tr className="table__row">
          <td className="table__cell">email-classifier</td>
          <td className="table__cell table__cell--mono">2026-03-25 09:09:00</td>
          <td className="table__cell table__cell--mono">12s</td>
          <td className="table__cell"><span className="badge badge--neutral">Completed</span></td>
        </tr>
      </tbody>
    </table>
  ),
};

export const Empty: Story = {
  render: () => (
    <table className="table">
      <thead className="table__head">
        <tr>
          <th className="table__header">Workflow</th>
          <th className="table__header">Status</th>
          <th className="table__header">Started</th>
        </tr>
      </thead>
      <tbody className="table__body">
        <tr>
          <td className="table__empty" colSpan={3}>No workflows found.</td>
        </tr>
      </tbody>
    </table>
  ),
};
