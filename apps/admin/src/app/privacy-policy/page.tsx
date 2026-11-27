import type { Metadata } from "next";
import { Suspense } from "react";
import PublicLegalPage from "@/components/public-legal-page";

export const metadata: Metadata = { title: "Privacy Policy | EnerTech", description: "EnerTech Privacy Policy" };

export default function PrivacyPolicyPage() {
  return <Suspense fallback={<main className="min-h-screen bg-base-200 p-8 text-base-content">Loading Privacy Policy…</main>}><PublicLegalPage documentKey="privacy_policy" /></Suspense>;
}
