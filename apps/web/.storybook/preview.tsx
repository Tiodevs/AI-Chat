import type { Preview } from "@storybook/react-vite"
import { MemoryRouter } from "react-router"

import { AppProviders } from "../src/app/providers.tsx"
import "../src/styles/globals.css"

if (typeof document !== "undefined") {
  document.documentElement.classList.add("dark")
  document.documentElement.lang = "pt-BR"
}

const preview: Preview = {
  decorators: [
    (Story) => (
      <AppProviders>
        <MemoryRouter>
          <div className="bg-background p-6 text-foreground">
            <Story />
          </div>
        </MemoryRouter>
      </AppProviders>
    ),
  ],
  parameters: {
    a11y: {
      test: "error",
    },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
  },
}

export default preview
