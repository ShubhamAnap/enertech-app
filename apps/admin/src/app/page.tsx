"use client";

import AdminShell from "@/components/admin-shell";
import AuthGate from "@/components/auth-gate";

export default function Home() {
  return <AuthGate>{(user, role) => <AdminShell user={user} role={role} />}</AuthGate>;
}
