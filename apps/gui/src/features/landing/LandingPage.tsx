import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { ChevronRight } from "lucide-react";

const RUNSIGHT_LOGO_SVG = (
  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="12" cy="5" r="2.5" fill="var(--primary)" />
    <circle cx="5" cy="17" r="2.5" fill="var(--primary)" opacity="0.7" />
    <circle cx="19" cy="17" r="2.5" fill="var(--primary)" opacity="0.7" />
    <circle cx="12" cy="13" r="1.5" fill="var(--primary)" opacity="0.5" />
    <line
      x1="12"
      y1="7.5"
      x2="12"
      y2="11.5"
      stroke="var(--primary)"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
    <line
      x1="10.8"
      y1="14"
      x2="6.5"
      y2="15.5"
      stroke="var(--primary)"
      strokeWidth="1.5"
      strokeLinecap="round"
      opacity="0.6"
    />
    <line
      x1="13.2"
      y1="14"
      x2="17.5"
      y2="15.5"
      stroke="var(--primary)"
      strokeWidth="1.5"
      strokeLinecap="round"
      opacity="0.6"
    />
  </svg>
);

const FLOATING_NODE_SVGS = [
  <svg key="1" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="1.5">
    <circle cx="12" cy="12" r="8" />
    <circle cx="12" cy="12" r="3" />
  </svg>,
  <svg key="2" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="1.5">
    <rect x="4" y="4" width="16" height="16" rx="2" />
    <path d="M8 12h8M12 8v8" />
  </svg>,
  <svg key="3" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--running)" strokeWidth="1.5">
    <polygon points="5 3 19 12 5 21 5 3" />
  </svg>,
  <svg key="4" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="1.5">
    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
  </svg>,
  <svg key="5" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="var(--muted-foreground)" strokeWidth="1.5">
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
  </svg>,
  <svg key="6" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="1.5">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
    <polyline points="10 9 9 9 8 9" />
  </svg>,
];

const FLOATING_NODE_POSITIONS = [
  { top: "15%", left: "10%", size: 48 },
  { top: "25%", right: "15%", size: 64 },
  { bottom: "30%", left: "8%", size: 40 },
  { bottom: "20%", right: "10%", size: 48 },
  { top: "60%", left: "15%", size: 56 },
  { top: "40%", right: "8%", size: 44 },
];

export function Component() {
  return (
    <div className="relative min-h-screen bg-[var(--background)] text-[var(--foreground)] overflow-x-hidden">
      {/* Background Grid */}
      <div
        className="fixed inset-0 pointer-events-none z-0"
        style={{
          backgroundImage: `
            radial-gradient(circle at 20% 80%, var(--primary-08) 0%, transparent 50%),
            radial-gradient(circle at 80% 20%, var(--running-05) 0%, transparent 40%),
            linear-gradient(var(--border-15) 1px, transparent 1px),
            linear-gradient(90deg, var(--border-15) 1px, transparent 1px)
          `,
          backgroundSize: "100% 100%, 100% 100%, 60px 60px, 60px 60px",
        }}
      />

      {/* Floating Decorative Nodes */}
      {FLOATING_NODE_SVGS.map((svg, i) => {
        const pos = FLOATING_NODE_POSITIONS[i];
        if (!pos) return null;
        return (
          <div
            key={i}
            className="absolute flex items-center justify-center rounded-[6px] bg-[var(--card)] border border-[var(--border)] opacity-60"
            style={{
              width: pos.size,
              height: pos.size,
              top: "top" in pos ? pos.top : undefined,
              left: "left" in pos ? pos.left : undefined,
              right: "right" in pos ? pos.right : undefined,
              bottom: "bottom" in pos ? pos.bottom : undefined,
              animation: "float 8s ease-in-out infinite",
              animationDelay: `${i % 4}s`,
            }}
          >
            {svg}
          </div>
        );
      })}

      {/* Main Content */}
      <main className="relative z-10 min-h-screen flex flex-col items-center justify-center px-8 py-32">
        {/* Logo */}
        <div className="flex items-center gap-[12px] mb-8">
          <div className="w-12 h-12 [&>svg]:w-full [&>svg]:h-full">
            {RUNSIGHT_LOGO_SVG}
          </div>
          <span className="text-[13px] font-semibold tracking-[0.08em] uppercase text-[var(--foreground)]">
            RUNSIGHT
          </span>
        </div>

        {/* Hero */}
        <div className="text-center max-w-[720px]">
          <h1 className="text-2xl font-semibold leading-[1.3] tracking-[-0.02em] text-[var(--foreground)] mb-6">
            Orchestrate AI Agents.
            <br />
            Visually.
          </h1>
          <p className="text-lg leading-[1.6] text-[var(--muted-foreground)] mb-10 max-w-[560px] mx-auto">
            A visual workflow builder for composing, monitoring, and managing multi-agent systems.
            Git-native, multi-provider, and designed for the way modern teams work.
          </p>
          <Link to="/onboarding">
            <Button className="h-9 px-4 text-sm font-medium rounded-md shadow-[0_4px_20px_var(--primary-30)] transition-all duration-150 hover:translate-y-[-1px] hover:shadow-[0_6px_24px_var(--primary-40)]">
              <span className="inline-flex items-center gap-2">
                Get Started
                <ChevronRight className="size-5" strokeWidth={2} />
              </span>
            </Button>
          </Link>
        </div>

        {/* Feature Grid */}
        <div className="grid grid-cols-3 gap-6 mt-16 max-w-[880px] max-md:grid-cols-2 max-md:gap-4">
          <div className="flex flex-col items-center text-center gap-3">
            <div className="w-12 h-12 flex items-center justify-center bg-[var(--card)] border border-[var(--border)] rounded-lg text-primary">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="w-6 h-6"
              >
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M3 9h18M9 21V9" />
              </svg>
            </div>
            <span className="text-[14px] font-medium text-[var(--foreground)]">Visual Canvas</span>
            <span className="text-[12px] text-[var(--muted-subtle)] leading-snug">Drag-and-drop workflow builder</span>
          </div>
          <div className="flex flex-col items-center text-center gap-3">
            <div className="w-12 h-12 flex items-center justify-center bg-[var(--card)] border border-[var(--border)] rounded-lg text-primary">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="w-6 h-6"
              >
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
            </div>
            <span className="text-[14px] font-medium text-[var(--foreground)]">Git-Native</span>
            <span className="text-[12px] text-[var(--muted-subtle)] leading-snug">YAML workflows, versioned by default</span>
          </div>
          <div className="flex flex-col items-center text-center gap-3">
            <div className="w-12 h-12 flex items-center justify-center bg-[var(--card)] border border-[var(--border)] rounded-lg text-primary">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="w-6 h-6"
              >
                <circle cx="12" cy="12" r="10" />
                <path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
              </svg>
            </div>
            <span className="text-[14px] font-medium text-[var(--foreground)]">Multi-Provider</span>
            <span className="text-[12px] text-[var(--muted-subtle)] leading-snug">OpenAI, Anthropic, local models</span>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer
        className="absolute bottom-6 left-1/2 -translate-x-1/2 text-[12px] text-[var(--muted-subtle)] z-10"
      >
        Linear meets Figma meets VS Code
      </footer>
    </div>
  );
}
