export const TAB_KEYS = ["overview", "data", "predict", "history", "training", "network", "settings"] as const;
export type Tab = (typeof TAB_KEYS)[number];
