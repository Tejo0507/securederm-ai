import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard",
  description: "Your hospital node: datasets, diagnoses, history, training and the network.",
  // Signed-in workspace; nothing here is useful in search results.
  robots: { index: false },
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return children;
}
