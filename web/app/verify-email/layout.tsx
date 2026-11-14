import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Verify email",
  description: "Confirm your hospital's email address to finish registration.",
};

export default function VerifyEmailLayout({ children }: { children: React.ReactNode }) {
  return children;
}
