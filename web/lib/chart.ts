/**
 * Recharts styling shared by every chart. Colors reference the CSS tokens, so
 * charts follow light and dark mode without any JavaScript theme switch.
 */
export const chart = {
  series: "rgb(var(--accent))",
  seriesAlt: "rgb(var(--warn))",
  grid: "rgb(var(--line))",
  axisTick: { fill: "rgb(var(--ink-3))", fontSize: 11, fontFamily: "var(--font-mono)" },
  cursor: { stroke: "rgb(var(--line-strong))", strokeWidth: 1 },
  barCursor: { fill: "rgb(var(--ink) / 0.04)" },
  tooltip: {
    contentStyle: {
      background: "rgb(var(--surface))",
      border: "1px solid rgb(var(--line))",
      borderRadius: 6,
      boxShadow: "0 8px 24px -8px rgb(var(--shadow) / 0.25)",
      fontSize: 12,
      padding: "8px 10px",
    },
    labelStyle: { color: "rgb(var(--ink-3))", fontFamily: "var(--font-mono)", fontSize: 11, marginBottom: 2 },
    itemStyle: { color: "rgb(var(--ink))", padding: 0 },
  },
} as const;
