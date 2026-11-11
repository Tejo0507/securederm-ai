"use client";

import { MotionConfig } from "framer-motion";
import ConfirmProvider from "@/components/ConfirmProvider";

/** App-wide client context: motion honours the OS reduced-motion setting everywhere. */
export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      <ConfirmProvider>{children}</ConfirmProvider>
    </MotionConfig>
  );
}
