"use client";

import { MotionConfig } from "framer-motion";
import ConfirmProvider from "@/components/ConfirmProvider";
import { ThemeProvider } from "@/lib/theme";

/**
 * App-wide client context: the color theme, and motion that honours the OS
 * reduced-motion setting everywhere.
 */
export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <MotionConfig reducedMotion="user">
        <ConfirmProvider>{children}</ConfirmProvider>
      </MotionConfig>
    </ThemeProvider>
  );
}
