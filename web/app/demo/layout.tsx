import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Live simulation",
  description:
    "Watch a simulated federated training round: local training, noised updates, FedAvg and redeployment.",
};

export default function DemoLayout({ children }: { children: React.ReactNode }) {
  return children;
}
