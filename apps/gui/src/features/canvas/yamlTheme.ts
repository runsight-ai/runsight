import type { editor } from "monaco-editor";

const THEME_NAME = "runsight-yaml";

function getCssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Convert any CSS color (hsl, rgb, hex, named) to a 6-digit hex string. */
function toHex(color: string): string {
  const ctx = document.createElement("canvas").getContext("2d")!;
  ctx.fillStyle = color;
  // fillStyle normalizes to #rrggbb or rgba(...)
  const norm = ctx.fillStyle;
  if (norm.startsWith("#")) return norm.slice(1);
  // rgba(r, g, b, a) fallback
  const m = norm.match(/(\d+)/g);
  if (!m) return "cccccc";
  return m
    .slice(0, 3)
    .map((v) => Number(v).toString(16).padStart(2, "0"))
    .join("");
}

export function defineYamlTheme(monaco: { editor: typeof editor }) {
  const syntaxKey = toHex(getCssVar("--syntax-key"));
  const syntaxString = toHex(getCssVar("--syntax-string"));
  const syntaxValue = toHex(getCssVar("--syntax-value"));
  const syntaxComment = toHex(getCssVar("--syntax-comment"));
  const syntaxPunct = toHex(getCssVar("--syntax-punct"));
  const bg = toHex(getCssVar("--surface-primary"));
  const fg = toHex(getCssVar("--text-primary"));

  monaco.editor.defineTheme(THEME_NAME, {
    base: "vs-dark",
    inherit: false,
    rules: [
      { token: "type", foreground: syntaxKey },
      { token: "key", foreground: syntaxKey },
      { token: "string", foreground: syntaxString },
      { token: "string.yaml", foreground: syntaxString },
      { token: "number", foreground: syntaxValue },
      { token: "number.yaml", foreground: syntaxValue },
      { token: "keyword", foreground: syntaxValue },
      { token: "comment", foreground: syntaxComment },
      { token: "delimiter", foreground: syntaxPunct },
      { token: "", foreground: fg },
    ],
    colors: {
      "editor.background": "#" + bg,
      "editor.foreground": "#" + fg,
    },
  });
}

export { THEME_NAME };
