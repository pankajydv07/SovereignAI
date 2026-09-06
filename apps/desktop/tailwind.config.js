import designTokens from "@swaraj/design-tokens";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: designTokens.theme,
  plugins: [],
};
