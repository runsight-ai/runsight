import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

const tsFiles = ["**/*.{ts,tsx,mts,cts}"];
const allCodeFiles = ["**/*.{ts,tsx,js,jsx,mjs,cjs}"];

export default tseslint.config(
  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "**/storybook-static/**",
      "**/playwright-report/**",
      "**/test-results/**",
      "**/.turbo/**",
      "**/coverage/**",
      "**/.vite/**",
      "**/*.d.ts",
      "packages/shared/src/api.ts",
      "packages/shared/src/zod.ts",
    ],
  },
  {
    files: allCodeFiles,
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
  },
  ...tseslint.configs.recommended.map((config) => ({
    ...config,
    files: tsFiles,
  })),
  {
    files: tsFiles,
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    plugins: {
      "@typescript-eslint": tseslint.plugin,
      "react-hooks": reactHooks,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "no-debugger": "error",
      "no-console": [
        "warn",
        {
          allow: ["error", "warn"],
        },
      ],
      "no-undef": "off",
      "@typescript-eslint/consistent-type-imports": [
        "error",
        {
          prefer: "type-imports",
          fixStyle: "inline-type-imports",
        },
      ],
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-empty-object-type": "off",
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
      "react-hooks/refs": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/exhaustive-deps": "error",
    },
  },
  {
    files: ["**/*.stories.{ts,tsx}", "**/__tests__/**/*.{ts,tsx}", "testing/gui-e2e/**/*.{ts,tsx}"],
    rules: {
      "no-console": "off",
    },
  },
  {
    files: ["packages/ui/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            "@/",
            "@/*",
            "@runsight/shared/src/*",
            "@runsight/gui/*",
          ],
        },
      ],
    },
  },
  {
    files: ["packages/ui/src/**/*.{ts,tsx}", "packages/shared/src/**/*.{ts,tsx}"],
    rules: {
      "no-console": "error",
    },
  },
  {
    files: ["packages/shared/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "react",
              message: "Shared must stay runtime-agnostic and contract-only.",
            },
            {
              name: "react-dom",
              message: "Shared must stay runtime-agnostic and contract-only.",
            },
          ],
          patterns: [
            "@/",
            "@/*",
            "@runsight/ui",
            "@runsight/ui/*",
            "@runsight/shared/src/*",
          ],
        },
      ],
    },
  },
  {
    files: ["apps/gui/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            "@runsight/ui/src/*",
            "@runsight/shared/src/*",
            "../../packages/ui/*",
            "../../../packages/ui/*",
            "../../../../packages/ui/*",
            "../../packages/shared/*",
            "../../../packages/shared/*",
            "../../../../packages/shared/*",
          ],
        },
      ],
    },
  },
);
