import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";
import reactHooks from "eslint-plugin-react-hooks";

const HARD_CODED_COLOR_PATTERN = "(#[0-9A-Fa-f]{3,8}\\b|rgba?\\()";

export default [
  {
    ignores: ["dist/**", "node_modules/**", "playwright-report/**", "e2e-screenshots/**"],
  },
  {
    files: ["src/**/*.{ts,tsx,js,jsx}"],
    languageOptions: {
      parser: tsParser,
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
      "react-hooks": reactHooks,
    },
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: `Literal[value=/${HARD_CODED_COLOR_PATTERN}/]`,
          message: "Use semantic CSS variables from globals.css instead of hardcoded colors.",
        },
        {
          selector: `TemplateElement[value.raw=/${HARD_CODED_COLOR_PATTERN}/]`,
          message: "Use semantic CSS variables from globals.css instead of hardcoded colors.",
        },
      ],
    },
  },
];
