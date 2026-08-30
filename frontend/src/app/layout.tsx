import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Open Supply-Chain Lifecycle Tracker",
  description: "EU DPP-aligned Digital Product Passport system — verifiable, cryptographic supply-chain provenance.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[var(--background)] text-[var(--foreground)] antialiased">
        {children}
      </body>
    </html>
  );
}
