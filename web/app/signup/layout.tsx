import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Register your hospital",
  description: "Create a SecureDerm node and join the federated wound-imaging network.",
};

export default function SignupLayout({ children }: { children: React.ReactNode }) {
  return children;
}
