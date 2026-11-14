import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Models",
  description:
    "Federated wound models published by the SecureDerm hospital network, with accuracy and participating sites.",
};

export default function ModelsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
