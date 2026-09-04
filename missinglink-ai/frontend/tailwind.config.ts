import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#0f3d91",
          light: "#1c5cd6",
          dark: "#0a2b66",
          ink: "#0b1b33",
        },
        accent: "#e05e2b",
      },
    },
  },
  plugins: [],
};
export default config;
