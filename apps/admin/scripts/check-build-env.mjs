import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { loadEnvConfig } = require("@next/env");
loadEnvConfig(process.cwd(), false);

const fallbacks = {
  NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000/api/v1",
  NEXT_PUBLIC_FIREBASE_API_KEY: "AIzaSyAUbtbOGwZwjLLAacs5VZtJKwSZfyNAxW4",
  NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN: "enertech-ups.firebaseapp.com",
  NEXT_PUBLIC_FIREBASE_PROJECT_ID: "enertech-ups",
  NEXT_PUBLIC_FIREBASE_APP_ID: "1:423316048940:web:a7ea828ca35de54fea1589",
  NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID: "423316048940",
};

for (const [key, fallbackValue] of Object.entries(fallbacks)) {
  if (!process.env[key]?.trim()) {
    process.env[key] = fallbackValue;
    console.log(`[check-build-env] Using fallback default for ${key}`);
  }
}

try {
  new URL(process.env.NEXT_PUBLIC_API_BASE_URL);
} catch {
  process.env.NEXT_PUBLIC_API_BASE_URL = fallbacks.NEXT_PUBLIC_API_BASE_URL;
}

console.log("CMS public Firebase and API settings verified.");
