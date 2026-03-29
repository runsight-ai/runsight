import type { Preview } from "@storybook/react";
import "../src/styles/globals.css";

/**
 * Storybook Preview Configuration
 *
 * Fonts loaded via @font-face in globals.css:
 *   - Geist — primary product body font
 *   - JetBrains Mono — code/data/metrics font
 *   - Satoshi — display/headline font (via Fontshare)
 */

const preview: Preview = {
  parameters: {
    backgrounds: {
      default: "dark",
      values: [
        {
          name: "dark",
          value: "hsl(40, 12%, 8%)",
        },
        {
          name: "light",
          value: "hsl(40, 15%, 97%)",
        },
      ],
    },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
  },
};

export default preview;
