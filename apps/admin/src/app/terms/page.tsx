import type { Metadata } from "next";
import { Suspense } from "react";
import PublicLegalPage from "@/components/public-legal-page";

export const metadata: Metadata = { title: "Terms of Use | EnerTech", description: "EnerTech Terms of Use" };

export default function TermsPage() {
  return <Suspense fallback={<main className="min-h-screen bg-base-200 p-8 text-base-content">Loading Terms of Use…</main>}><PublicLegalPage documentKey="terms" /></Suspense>;
}
