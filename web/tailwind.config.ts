import type { Config } from "tailwindcss";

/** Every color is a CSS variable (see globals.css) so light and dark themes share one set of names. */
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: token("canvas"),
        surface: token("surface"),
        sunken: token("sunken"),
        line: token("line"),
        "line-strong": token("line-strong"),
        ink: token("ink"),
        "ink-2": token("ink-2"),
        "ink-3": token("ink-3"),
        accent: {
          DEFAULT: token("accent"),
          hover: token("accent-hover"),
          soft: token("accent-soft"),
          ink: token("accent-ink"),
          on: token("on-accent"),
        },
        danger: {
          DEFAULT: token("danger"),
          hover: token("danger-hover"),
          soft: token("danger-soft"),
          ink: token("danger-ink"),
        },
        warn: {
          DEFAULT: token("warn"),
          soft: token("warn-soft"),
          ink: token("warn-ink"),
        },
        ok: {
          DEFAULT: token("ok"),
          soft: token("ok-soft"),
          ink: token("ok-ink"),
        },
        night: {
          DEFAULT: token("night"),
          2: token("night-2"),
          line: token("night-line"),
          ink: token("night-ink"),
          muted: token("night-muted"),
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      borderRadius: {
        DEFAULT: "6px",
        md: "6px",
        lg: "10px",
        xl: "14px",
      },
      boxShadow: {
        raise: "0 1px 0 rgb(var(--shadow) / 0.04), 0 1px 3px rgb(var(--shadow) / 0.06)",
        float: "0 12px 32px -8px rgb(var(--shadow) / 0.22), 0 2px 6px rgb(var(--shadow) / 0.08)",
      },
      transitionTimingFunction: {
        out: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "none" },
        },
        shimmer: {
          from: { backgroundPosition: "200% 0" },
          to: { backgroundPosition: "-200% 0" },
        },
        "grow-x": {
          from: { transform: "scaleX(0)" },
          to: { transform: "scaleX(1)" },
        },
      },
      animation: {
        // Duration is usually overridden inline to match what it measures.
        "grow-x": "grow-x 1s linear both",
        "fade-up": "fade-up 360ms cubic-bezier(0.22, 1, 0.36, 1) both",
        shimmer: "shimmer 1.6s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
