import "./globals.css";
import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "MissingLink — Community-sourced missing persons platform",
  description:
    "AI-assisted, community-sourced platform to report missing persons and submit sighting leads.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-800">
        <AuthProvider>
          <Navbar />
          <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
          <footer className="border-t border-slate-200 bg-white py-6 text-center text-xs text-slate-400">
            MissingLink — this demo uses synthetic data. If someone is in danger,
            call your local emergency number.
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
