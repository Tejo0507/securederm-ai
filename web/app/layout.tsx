import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "SecureDerm AI — Privacy-Preserving Federated AI for Hospitals",
  description:
    "Train medical AI collaboratively across hospitals without exposing patient data. Powered by federated learning and differential privacy.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        className={`${inter.className} bg-[#09090b] text-white antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
