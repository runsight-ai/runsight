import type { StorybookConfig } from "@storybook/react-vite";
import { createRequire } from "node:module";
import tailwindcss from "@tailwindcss/vite";

const require = createRequire(import.meta.url);

const config: StorybookConfig = {
  stories: ["../src/**/*.stories.@(ts|tsx)"],
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  addons: ["@storybook/addon-essentials"],
  viteFinal(config) {
    config.plugins = [...(config.plugins ?? []), tailwindcss()];
    config.resolve ??= {};
    config.resolve.alias = {
      ...(config.resolve.alias ?? {}),
      "@storybook/react/dist/entry-preview.mjs": require.resolve(
        "@storybook/react/dist/entry-preview.mjs",
      ),
    };
    return config;
  },
};

export default config;
