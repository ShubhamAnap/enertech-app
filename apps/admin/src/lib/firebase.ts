import { getApp, getApps, initializeApp, type FirebaseApp } from "firebase/app";
import { connectAuthEmulator, getAuth, type Auth } from "firebase/auth";

let app: FirebaseApp | null = null;
let auth: Auth | null = null;

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || "",
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN || "",
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "",
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || "",
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID || "",
};

export function hasFirebaseConfig(): boolean {
  return Object.values(firebaseConfig).every((value) => value.trim().length > 0);
}

export function getFirebaseAuth(): Auth | null {
  if (typeof window === "undefined" || !hasFirebaseConfig()) return null;

  try {
    if (!app) {
      app = getApps().length
        ? getApp()
        : initializeApp(firebaseConfig);
    }
    if (!auth) {
      auth = getAuth(app);
      const emulator = process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST;
      if (emulator && !auth.emulatorConfig) {
        connectAuthEmulator(auth, `http://${emulator}`, { disableWarnings: true });
      }
    }
    return auth;
  } catch (error) {
    console.error("Firebase auth initialization error:", error);
    return null;
  }
}
