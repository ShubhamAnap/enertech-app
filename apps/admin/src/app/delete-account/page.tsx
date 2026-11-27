import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Account Deletion | EnerTech",
  description: "How to delete your EnerTech Customer account and what support history is retained.",
};

export default function DeleteAccountPage() {
  return (
    <main className="min-h-screen bg-base-200 px-4 py-8 text-base-content sm:py-12">
      <article className="card mx-auto max-w-3xl border border-base-300 bg-base-100 shadow-sm">
        <div className="card-body gap-6 sm:p-10">
          <header className="border-b border-base-300 pb-5">
            <Link className="link link-primary text-sm font-semibold" href="/">
              EnerTech
            </Link>
            <h1 className="mt-3 text-3xl font-bold text-primary sm:text-4xl">
              Account &amp; Data Deletion
            </h1>
            <p className="mt-2 text-sm text-base-content/70">
              EnerTech Customer Platform — Account removal &amp; equipment history policy
            </p>
          </header>

          <section className="space-y-3 leading-7">
            <h2 className="text-xl font-semibold text-primary">1. Delete Directly Inside the App</h2>
            <p>
              You can permanently delete your EnerTech Customer account at any time inside the
              mobile application:
            </p>
            <ol className="list-decimal space-y-1 pl-6">
              <li>Open the <strong>EnerTech</strong> app and sign in to your account.</li>
              <li>Go to the <strong>Account</strong> tab in the bottom navigation bar.</li>
              <li>Scroll down and tap <strong>Delete Account</strong>, then confirm permanent deletion.</li>
            </ol>
          </section>

          <section className="space-y-3 leading-7">
            <h2 className="text-xl font-semibold text-primary">2. Request Deletion Without the App</h2>
            <p>
              If you have uninstalled the app or cannot sign in, email{" "}
              <a className="link link-primary" href="mailto:support@enertechups.com?subject=Account%20Deletion%20Request">
                support@enertechups.com
              </a>{" "}
              from your registered email address with the subject <strong>Account Deletion Request</strong>.
              Our support team will verify ownership and process your deletion within 7 working days.
            </p>
          </section>

          <section className="space-y-3 leading-7">
            <h2 className="text-xl font-semibold text-primary">3. What Is Deleted vs. Preserved</h2>
            <ul className="list-disc space-y-2 pl-6">
              <li>
                <strong>Permanently Deleted:</strong> Your sign-in account (Firebase Authentication),
                full name, email address, mobile number, city/state location, company/business name,
                and GSTIN.
              </li>
              <li>
                <strong>Anonymized &amp; Preserved for Support Compliance:</strong> Equipment serial
                numbers, product models, purchase dates, service fault logs, quotation records, and
                warranty/AMC request statuses are detached from your identity and retained in
                anonymized form so EnerTech can honor equipment warranties and maintenance history.
              </li>
            </ul>
          </section>

          <footer className="flex flex-wrap gap-4 border-t border-base-300 pt-5 text-sm text-base-content/70">
            <Link className="link link-primary" href="/privacy-policy">
              Privacy Policy
            </Link>
            <Link className="link link-primary" href="/terms">
              Terms of Use
            </Link>
          </footer>
        </div>
      </article>
    </main>
  );
}
