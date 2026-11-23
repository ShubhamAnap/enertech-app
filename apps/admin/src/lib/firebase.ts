import { getApp, getApps, initializeApp, type FirebaseApp } from "firebase/app";
import { connectAuthEmulator, getAuth, type Auth } from "firebase/auth";

let app: FirebaseApp | null = null;
let auth: Auth | null = null;

const FIREBASE_API_KEY =
  process.env.NEXT_PUBLIC_FIREBASE_API_KEY ||
  "AIzaSyAUbtbOGwZwjLLAacs5VZtJKwSZfyNAxW4";
const FIREBASE_AUTH_DOMAIN =
  process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ||
  "enertech-ups.firebaseapp.com";
const FIREBASE_PROJECT_ID =
  process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "enertech-ups";
const FIREBASE_APP_ID =
  process.env.NEXT_PUBLIC_FIREBASE_APP_ID ||
  "1:423316048940:web:a7ea828ca35de54fea1589";
const FIREBASE_MESSAGING_SENDER_ID =
  process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID || "423316048940";

export function getFirebaseAuth(): Auth | null {
  if (typeof window === "undefined") return null;

  try {
    if (!app) {
      app = getApps().length
        ? getApp()
        : initializeApp({
            apiKey: FIREBASE_API_KEY,
            authDomain: FIREBASE_AUTH_DOMAIN,
            projectId: FIREBASE_PROJECT_ID,
            appId: FIREBASE_APP_ID,
            messagingSenderId: FIREBASE_MESSAGING_SENDER_ID,
          });
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

export function hasFirebaseConfig(): boolean {
  return true;
}
