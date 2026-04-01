import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const APP_SRC_DIR = resolve(__dirname, "../../..");
const FEATURE_DIR = resolve(APP_SRC_DIR, "features", "souls");
const ROUTES_PATH = resolve(APP_SRC_DIR, "routes", "index.tsx");
const PAGE_PATH = resolve(FEATURE_DIR, "SoulFormPage.tsx");
const FOOTER_PATH = resolve(FEATURE_DIR, "SoulFormFooter.tsx");

function read(path: string): string {
  return readFileSync(path, "utf-8");
}

describe("RUN-449 file creation", () => {
  it("creates SoulFormPage and SoulFormFooter under features/souls", () => {
    expect(existsSync(PAGE_PATH)).toBe(true);
    expect(existsSync(FOOTER_PATH)).toBe(true);
  });
});

describe("RUN-449 route wiring", () => {
  it("adds /souls/new and /souls/:id/edit routes that lazy-load SoulFormPage", () => {
    const routesSource = read(ROUTES_PATH);
    expect(routesSource).toMatch(/path:\s*["']souls\/new["']/);
    expect(routesSource).toMatch(/path:\s*["']souls\/:id\/edit["']/);
    expect(routesSource).toMatch(/SoulFormPage/);
  });
});

describe("SoulFormFooter contract (RUN-449)", () => {
  it("exports a sticky footer with mode/returnUrl label switching", () => {
    const source = read(FOOTER_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+SoulFormFooter/);
    expect(source).toMatch(/mode:\s*["']create["']\s*\|\s*["']edit["']/);
    expect(source).toMatch(/returnUrl:\s*string\s*\|\s*null/);
    expect(source).toMatch(/isDirty:\s*boolean/);
    expect(source).toMatch(/isSubmitting:\s*boolean/);
    expect(source).toMatch(/isValid:\s*boolean/);
    expect(source).toMatch(/onCancel/);
    expect(source).toMatch(/onSubmit/);
    expect(source).toMatch(/Save & Return to Canvas/);
    expect(source).toMatch(/Create Soul/);
    expect(source).toMatch(/Save Changes/);
    expect(source).toMatch(/sticky|bottom-0/);
  });
});

describe("SoulFormPage contract (RUN-449)", () => {
  it("exports a page component that assembles useSoul, useSoulForm, SoulFormBody, and SoulFormFooter", () => {
    const source = read(PAGE_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+(Component|SoulFormPage)/);
    expect(source).toMatch(/useParams/);
    expect(source).toMatch(/useSearchParams/);
    expect(source).toMatch(/useNavigate/);
    expect(source).toMatch(/useSoul\(/);
    expect(source).toMatch(/useSoulForm\(/);
    expect(source).toMatch(/SoulFormBody/);
    expect(source).toMatch(/SoulFormFooter/);
  });

  it("derives create vs edit mode from the route and renders matching breadcrumb/button copy", () => {
    const source = read(PAGE_PATH);
    expect(source).toMatch(/\/souls|["']Souls["']/);
    expect(source).toMatch(/New Soul/);
    expect(source).toMatch(/Edit/);
    expect(source).toMatch(/role/);
  });

  it("navigates to returnUrl on success when present, otherwise back to /souls", () => {
    const source = read(PAGE_PATH);
    expect(source).toMatch(/returnUrl/);
    expect(source).toMatch(/navigate\(\s*returnUrl/);
    expect(source).toMatch(/navigate\(\s*["']\/souls["']/);
  });

  it("derives workflow editor context from returnUrl so workflow tools can be shown during soul editing", () => {
    const source = read(PAGE_PATH);
    expect(source).toMatch(/returnUrl/);
    expect(source).toMatch(/workflows/);
    expect(source).toMatch(/workflowId|workflowContext|workflowTools/);
  });

  it("uses a blocker pattern for dirty navigation and shows discard/keep-editing controls", () => {
    const source = read(PAGE_PATH);
    expect(source).toMatch(/useBlocker/);
    expect(source).toMatch(/isDirty/);
    expect(source).toMatch(/Unsaved changes|unsaved changes/i);
    expect(source).toMatch(/Discard changes/);
    expect(source).toMatch(/Keep editing/);
    expect(source).toMatch(/blocker\.proceed|proceed\?/);
    expect(source).toMatch(/blocker\.reset|reset\?/);
  });

  it("renders a full-page loading shell for edit mode instead of inline loading copy", () => {
    const source = read(PAGE_PATH);
    expect(source).toMatch(/SoulFormLoadingState/);
    expect(source).toMatch(/subtitle=\s*["']Loading\.\.\.["']/);
    expect(source).not.toMatch(/Loading soul…|Loading soul\.\.\./);
  });

  it("uses a wider desktop form shell while keeping the sticky footer aligned to the same content width", () => {
    const source = read(PAGE_PATH);
    expect(source).toMatch(/max-w-4xl|max-w-5xl/);
  });
});
