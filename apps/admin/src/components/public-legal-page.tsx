import { notFound } from "next/navigation";
import Link from "next/link";

type LegalPage = {
  title: string;
  body: string;
  effective_date: string;
  version: number;
};

export default async function PublicLegalPage({ documentKey }: { documentKey: "privacy_policy" | "terms" }) {
  const api = (process.env.INTERNAL_API_URL || "http://api:8000").replace(/\/$/, "");
  const response = await fetch(`${api}/api/v1/legal/${documentKey}`, { cache: "no-store" });
  if (response.status === 404) notFound();
  if (!response.ok) throw new Error("The legal page is temporarily unavailable.");
  const document = await response.json() as LegalPage;
  const paragraphs = document.body.replace(/\r\n/g, "\n").split(/\n\s*\n/).map((part) => part.trim()).filter(Boolean);

  return <main className="min-h-screen bg-base-200 px-4 py-8 text-base-content sm:py-12">
    <article className="card mx-auto max-w-3xl border border-base-300 bg-base-100 shadow-sm">
      <div className="card-body gap-6 sm:p-10">
        <header className="border-b border-base-300 pb-5">
          <Link className="link link-primary text-sm font-semibold" href="/">EnerTech</Link>
          <h1 className="mt-3 text-3xl font-bold text-primary sm:text-4xl">{document.title}</h1>
          <p className="mt-2 text-sm text-base-content/70">Effective {new Date(`${document.effective_date}T00:00:00Z`).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" })}</p>
        </header>
        <div className="space-y-5 leading-7">
          {paragraphs.map((part, index) => {
            const heading = part.match(/^#{1,3}\s+(.+)$/);
            if (heading) return <h2 key={index} className="mt-8 text-xl font-semibold text-primary">{heading[1]}</h2>;
            return <p key={index} className="whitespace-pre-line break-words">{part}</p>;
          })}
        </div>
        <footer className="border-t border-base-300 pt-5 text-sm text-base-content/70">
          <Link className="link link-primary" href={documentKey === "privacy_policy" ? "/terms" : "/privacy-policy"}>{documentKey === "privacy_policy" ? "Terms of Use" : "Privacy Policy"}</Link>
        </footer>
      </div>
    </article>
  </main>;
}
