"use client";

import { onAuthStateChanged, signInWithEmailAndPassword, signOut, type User } from "firebase/auth";
import { useEffect, useState, type FormEvent } from "react";
import { getEffectiveApiBaseUrl } from "@/lib/api";
import { getFirebaseAuth, hasFirebaseConfig } from "@/lib/firebase";

type AccessState = "checking" | "allowed" | "denied" | "unavailable";

export default function AuthGate({ children }: { children: (user: User, role: string) => React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [role, setRole] = useState("");
  const [ready, setReady] = useState(false);
  const [access, setAccess] = useState<AccessState>("checking");
  const [accessMessage, setAccessMessage] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  useEffect(() => {
    let active = true;
    let authEvent = 0;
    let verificationController: AbortController | null = null;
    try {
      const auth = getFirebaseAuth();
      if (!auth) {
        void Promise.resolve().then(() => { if (active) setReady(true); });
        return;
      }

      const unsubscribe = onAuthStateChanged(auth, async (next) => {
        if (!active) return;
        const currentEvent = ++authEvent;
        verificationController?.abort();
        verificationController = null;
        setUser(next);
        setReady(true);
        setAccessMessage("");

        if (!next) {
          setRole("");
          setAccess("denied");
          return;
        }

        setAccess("checking");
        const controller = new AbortController();
        verificationController = controller;
        try {
          const timeout = setTimeout(() => controller.abort(), 6000);
          const response = await fetch(`${getEffectiveApiBaseUrl()}/admin/session`, {
            headers: { Authorization: `Bearer ${await next.getIdToken()}`, Accept: "application/json" },
            cache: "no-store",
            signal: controller.signal,
          }).finally(() => clearTimeout(timeout));
          if (!active || currentEvent !== authEvent || controller.signal.aborted) return;
          if (!response.ok) {
            setRole("");
            setAccess(response.status === 401 || response.status === 403 ? "denied" : "unavailable");
            setAccessMessage(response.status === 401 || response.status === 403
              ? "This account is not authorized for the CMS. Ask a super-admin to grant access."
              : "The CMS could not verify your role. Check the API connection and try again.");
            return;
          }
          const session = await response.json().catch(() => null) as { role?: string } | null;
          if (!active || currentEvent !== authEvent || controller.signal.aborted) return;
          if (!session?.role) throw new Error("The API did not return an administrator role.");
          setRole(session.role);
          setAccess("allowed");
        } catch {
          if (!active || currentEvent !== authEvent || controller.signal.aborted) return;
          setRole("");
          setAccess("unavailable");
          setAccessMessage("The CMS could not verify your role. Check the API connection and try again.");
        }
      });

      return () => {
        active = false;
        authEvent += 1;
        verificationController?.abort();
        unsubscribe();
      };
    } catch {
      void Promise.resolve().then(() => { if (active) setReady(true); });
    }
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setWorking(true);
    try {
      const auth = getFirebaseAuth();
      if (!auth) throw new Error("Firebase is not initialized.");
      await signInWithEmailAndPassword(auth, email.trim(), password);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message.replace("Firebase: ", "") : "Sign-in failed. Check your details and try again.");
    } finally {
      setWorking(false);
    }
  }

  if (!hasFirebaseConfig()) {
    return (
      <main className="grid min-h-screen place-items-center bg-base-200 p-5">
        <section className="card w-full max-w-md border border-base-300 bg-base-100 shadow-sm">
          <div className="card-body gap-3 p-7 sm:p-9">
            <p className="eyebrow">ENERTECH · ADMIN</p>
            <h1 className="text-2xl font-bold text-secondary">CMS setup is incomplete</h1>
            <p className="text-sm text-base-content/70">Configure the public Firebase web app values for this deployment before signing in.</p>
          </div>
        </section>
      </main>
    );
  }

  // 1. Initial mounting state (until client mounts)
  if (!ready) {
    return (
      <main className="grid min-h-screen place-items-center">
        <span className="loading loading-spinner loading-lg text-primary" aria-label="Loading CMS workspace" />
      </main>
    );
  }

  // 2. Authenticated with allowed access
  if (user && access === "allowed") {
    return <>{children(user, role)}</>;
  }

  // 3. Authenticated but checking backend session
  if (user && access === "checking") {
    return (
      <main className="grid min-h-screen place-items-center">
        <span className="loading loading-spinner loading-lg text-primary" aria-label="Verifying admin session" />
      </main>
    );
  }

  if (user && (access === "denied" || access === "unavailable")) {
    return (
      <main className="grid min-h-screen place-items-center bg-base-200 p-5">
        <section className="card w-full max-w-md border border-base-300 bg-base-100 shadow-sm">
          <div className="card-body gap-4 p-7 sm:p-9">
            <p className="eyebrow">ENERTECH · ADMIN</p>
            <h1 className="text-2xl font-bold text-secondary">{access === "denied" ? "CMS access not granted" : "Could not verify CMS access"}</h1>
            <p role="alert" className="text-sm text-base-content/70">{accessMessage}</p>
            {access === "unavailable" && <button className="btn btn-primary" onClick={() => window.location.reload()}>Retry verification</button>}
            <button className="btn btn-ghost" onClick={() => { const auth = getFirebaseAuth(); if (auth) void signOut(auth); }}>Sign out</button>
          </div>
        </section>
      </main>
    );
  }

  // 4. Default: Sign-in Form
  return (
    <main className="grid min-h-screen place-items-center bg-base-200 p-5">
      <form onSubmit={submit} className="card w-full max-w-md border border-base-300 bg-base-100 shadow-sm">
        <div className="card-body gap-5 p-7 sm:p-9">
          <span className="brand-mark">E</span>
          <div>
            <p className="eyebrow">ENERTECH · ADMIN</p>
            <h1 className="text-2xl font-bold text-secondary">Sign in to your workspace</h1>
            <p className="mt-2 text-sm text-base-content/60">Use a Firebase account that has an active CMS role.</p>
          </div>
          {error && <div role="alert" className="alert alert-error text-sm">{error}</div>}
          <label className="form-control gap-1.5">
            <span className="label-text font-medium">Work email</span>
            <input
              className="input input-bordered w-full"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label className="form-control gap-1.5">
            <span className="label-text font-medium">Password</span>
            <input
              className="input input-bordered w-full"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <button className="btn btn-primary w-full" disabled={working}>
            {working ? <span className="loading loading-spinner loading-sm" /> : "Sign in"}
          </button>
          <p className="text-xs leading-5 text-base-content/55">
            Protected by Firebase Authentication. Only accounts with an active CMS role can access this workspace.
          </p>
        </div>
      </form>
    </main>
  );
}

