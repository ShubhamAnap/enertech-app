"use client";

import { onAuthStateChanged, signInWithEmailAndPassword, signOut, type User } from "firebase/auth";
import { useEffect, useState, type FormEvent } from "react";
import { getFirebaseAuth, hasFirebaseConfig } from "@/lib/firebase";

type AccessState = "checking" | "allowed" | "denied" | "unavailable";

export default function AuthGate({ children }: { children: (user: User, role: string) => React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [role, setRole] = useState("");
  const [ready, setReady] = useState(() => !hasFirebaseConfig());
  const authAvailable = hasFirebaseConfig();
  const [access, setAccess] = useState<AccessState>("checking");
  const [accessMessage, setAccessMessage] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  useEffect(() => {
    const auth = getFirebaseAuth();
    if (!auth) return;
    let active = true;
    const unsubscribe = onAuthStateChanged(auth, async (next) => {
      if (!active) return;
      setUser(next); setReady(true); setAccessMessage("");
      if (!next) { setRole(""); setAccess("denied"); return; }
      setAccess("checking");
      try {
        const base = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
        if (!base) throw new Error("The CMS API URL is not configured.");
        const response = await fetch(`${base}/admin/session`, { headers: { Authorization: `Bearer ${await next.getIdToken()}`, Accept: "application/json" }, cache: "no-store" });
        if (!active) return;
        if (response.ok) {
          const session = await response.json().catch(() => null) as { role?: string } | null;
          if (!active) return;
          setRole(session?.role ?? "content_editor"); setAccess("allowed"); return;
        }
        const payload = await response.json().catch(() => null) as { detail?: string } | null;
        if (response.status === 401 || response.status === 403) {
          setAccess("denied"); setAccessMessage(response.status === 403 ? "This Firebase account has not been granted a CMS role." : payload?.detail ?? "Sign in again to continue.");
        } else { setAccess("unavailable"); setAccessMessage(payload?.detail ?? `The CMS API returned ${response.status}.`); }
      } catch (cause) {
        if (!active) return;
        setAccess("unavailable"); setAccessMessage(cause instanceof Error ? cause.message : "Could not verify CMS access.");
      }
    });
    return () => { active = false; unsubscribe(); };
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setWorking(true);
    try { const auth = getFirebaseAuth(); if (!auth) throw new Error("Firebase is not configured."); await signInWithEmailAndPassword(auth, email.trim(), password); }
    catch (cause) { setError(cause instanceof Error ? cause.message.replace("Firebase: ", "") : "Sign-in failed. Check your details and try again."); }
    finally { setWorking(false); }
  }

  if (!ready || (user && access === "checking")) return <main className="grid min-h-screen place-items-center"><span className="loading loading-spinner loading-lg text-primary" aria-label="Checking sign-in and CMS access"/></main>;
  if (!authAvailable || !hasFirebaseConfig()) return <SetupScreen/>;
  if (user && access === "allowed") return <>{children(user, role)}</>;
  if (user && (access === "denied" || access === "unavailable")) return <main className="grid min-h-screen place-items-center bg-base-200 p-5"><section className="card w-full max-w-lg border border-base-300 bg-base-100 shadow-sm"><div className="card-body gap-4 p-7"><span className="brand-mark">E</span><p className="eyebrow">CMS ACCESS</p><h1 className="text-2xl font-bold text-secondary">{access === "denied" ? "Admin access required" : "Could not verify access"}</h1><p className="text-sm leading-6 text-base-content/65">{accessMessage}</p><div className="flex gap-2"><button className="btn btn-outline" onClick={() => { setAccess("checking"); setAccessMessage(""); void user.getIdToken(true).then(() => window.location.reload()); }}>Retry</button><button className="btn btn-primary" onClick={() => { const auth = getFirebaseAuth(); if (auth) void signOut(auth); }}>Sign out</button></div></div></section></main>;
  return <main className="grid min-h-screen place-items-center bg-base-200 p-5"><form onSubmit={submit} className="card w-full max-w-md border border-base-300 bg-base-100 shadow-sm"><div className="card-body gap-5 p-7 sm:p-9"><span className="brand-mark">E</span><div><p className="eyebrow">ENERTECH · ADMIN</p><h1 className="text-2xl font-bold text-secondary">Sign in to your workspace</h1><p className="mt-2 text-sm text-base-content/60">Use an authorized admin account to continue.</p></div>{error && <div role="alert" className="alert alert-error text-sm">{error}</div>}<label className="form-control gap-1.5"><span className="label-text font-medium">Work email</span><input className="input input-bordered w-full" type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)}/></label><label className="form-control gap-1.5"><span className="label-text font-medium">Password</span><input className="input input-bordered w-full" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)}/></label><button className="btn btn-primary w-full" disabled={working}>{working ? <span className="loading loading-spinner loading-sm"/> : "Sign in"}</button><p className="text-xs leading-5 text-base-content/55">There is no public admin signup. CMS access is provisioned and authorized on the server.</p></div></form></main>;
}

function SetupScreen() {
  return <main className="grid min-h-screen place-items-center p-5"><section className="card w-full max-w-lg border border-base-300 bg-base-100 shadow-sm"><div className="card-body gap-4 p-7 sm:p-9"><span className="brand-mark">E</span><div><p className="eyebrow">CMS CONNECTION SETUP</p><h1 className="text-2xl font-bold text-secondary">Connect Firebase Authentication</h1></div><p className="text-sm leading-6 text-base-content/65">The admin console is locked until Firebase is configured. Copy <code>apps/admin/.env.example</code> to <code>.env.local</code> and add the public Firebase web app values. Server credentials belong only in <code>backend/.env</code> or Coolify secrets.</p><div className="alert alert-info text-sm">No account creation is available here. Admin access is granted by the backend allowlist and role records.</div></div></section></main>;
}
