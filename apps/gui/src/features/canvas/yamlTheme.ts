import type { editor } from "monaco-editor";

const THEME_NAME = "runsight-yaml";

function getCssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function defineYamlTheme(monaco: { editor: typeof editor }) {
  const syntaxKey = getCssVar("--syntax-key");
  const syntaxString = getCssVar("--syntax-string");
  const syntaxValue = getCssVar("--syntax-value");
  const syntaxComment = getCssVar("--syntax-comment");
  const syntaxPunct = getCssVar("--syntax-punct");
  const bg = getCssVar("--surface-primary");
  const fg = getCssVar("--text-primary");

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
      "editor.background": bg,
      "editor.foreground": fg,
    },
  });
}

export { THEME_NAME };
