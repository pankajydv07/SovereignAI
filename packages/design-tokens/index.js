module.exports = {
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        border: "var(--border)",
        hairline: "var(--hairline)",
        text: "var(--text)",
        "text-dim": "var(--text-dim)",
        "text-faint": "var(--text-faint)",
        accent: "var(--accent)",
        sovereign: "var(--sovereign)",
        verify: "var(--verify)",
        critical: "var(--critical)",
        planner: "var(--tint-planner)",
        coder: "var(--tint-coder)",
        vision: "var(--tint-vision)",
        ocr: "var(--tint-ocr)",
      },
      fontSize: {
        base: ["13px", "1.45"],
        xs: ["11px", "1.3"],
        sm: ["12px", "1.4"],
        lg: ["14px", "1.45"],
        xl: ["16px", "1.4"],
      },
      borderRadius: {
        DEFAULT: "4px",
        sm: "4px",
        md: "6px",
      },
      height: {
        topbar: "44px",
        row: "30px",
      },
      width: {
        leftrail: "56px",
      },
      transitionDuration: {
        400: "400ms",
      },
    },
  },
};
