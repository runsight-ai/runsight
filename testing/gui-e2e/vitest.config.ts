import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/governance/*.test.ts"],
    maxWorkers: 1,
    fileParallelism: false,
  },
});
