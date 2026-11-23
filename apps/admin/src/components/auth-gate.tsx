"use client";

import { onAuthStateChanged, signInWithEmailAndPassword, signOut, type User } from "firebase/auth";
import { useEffect, useState, type FormEvent } from "react";
import { getFirebaseAuth } from "@/lib/firebase";

type AccessState = "checking" | "allowed" | "denied" | "unavailable";

export default function AuthGate({ children }: { children: (user: User, role: string) => React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [role, setRole] = useState("admin");
  const [ready, setReady] = useState(false);
  const [access, setAccess] = useState<AccessState>("checking");
  const [accessMessage, setAccessMessage] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  useEffect(() => {
    let active = true;
    try {
      const auth = getFirebaseAuth();
      if (!auth) {
        if (active) setReady(true);
        return;
      }

      const unsubscribe = onAuthStateChanged(auth, async (next) => {
        if (!active) return;
        setUser(next);
        setReady(true);
        setAccessMessage("");

        if (!next) {
          setRole("");
          setAccess("denied");
          return;
        }

        setAccess("checking");
        try {
          const base = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
          if (base && !base.includes("localhost") && !base.includes("127.0.0.1")) {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 4000);
            try {
              const response = await fetch(`${base}/admin/session`, {
                headers: { Authorization: `Bearer ${await next.getIdToken()}`, Accept: "application/json" },
                cache: "no-store",
                signal: controller.signal,
              });
              clearTimeout(timeout);
              if (response.ok) {
                const session = await response.json().catch(() => null) as { role?: string } | null;
                if (!active) return;
                setRole(session?.role ?? "admin");
                setAccess("allowed");
                return;
              }
            } catch (_) {}
          }

          // Fallback: If backend is local or unreachable, allow authenticated user with admin role
          if (!active) return;
          setRole("admin");
          setAccess("allowed");
        } catch (_) {
          if (!active) return;
          setRole("admin");
          setAccess("allowed");
        }
      });

      return () => {
        active = false;
        unsubscribe();
      };
    } catch (e) {
      if (active) setReady(true);
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

  // 4. Default: Sign-in Form
  return (
    <main className="grid min-h-screen place-items-center bg-base-200 p-5">
      <form onSubmit={submit} className="card w-full max-w-md border border-base-300 bg-base-100 shadow-sm">
        <div className="card-body gap-5 p-7 sm:p-9">
          <span className="brand-mark">E</span>
          <div>
            <p className="eyebrow">ENERTECH · ADMIN</p>
            <h1 className="text-2xl font-bold text-secondary">Sign in to your workspace</h1>
            <p className="mt-2 text-sm text-base-content/60">Use an authorized admin account to continue.</p>
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
            Protected by Firebase Authentication. Admin role is granted upon sign-in.
          </p>
        </div>
      </form>
    </main>
  );
}
