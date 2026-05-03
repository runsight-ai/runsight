import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      include: ["src/**/*.test.{ts,tsx}"],
      maxWorkers: 1,
      fileParallelism: false,
      coverage: {
        provider: "v8",
        include: ["src/**/*.{ts,tsx}"],
        exclude: [
          "src/**/*.d.ts",
          "src/**/*.test.{ts,tsx}",
          "src/**/__tests__/**",
          "src/test/**",
          "src/routeTree.gen.ts",
        ],
      },
    },
  }),
);
