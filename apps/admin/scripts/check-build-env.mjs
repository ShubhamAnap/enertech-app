import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { loadEnvConfig } = require("@next/env");
loadEnvConfig(process.cwd(), false);

const required = [
  "NEXT_PUBLIC_API_BASE_URL",
  "NEXT_PUBLIC_FIREBASE_API_KEY",
  "NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN",
  "NEXT_PUBLIC_FIREBASE_PROJECT_ID",
  "NEXT_PUBLIC_FIREBASE_APP_ID",
];
const missing = required.filter((key) => !process.env[key]?.trim());
if (missing.length) {
  console.error(`CMS build stopped: configure ${missing.join(", ")} in apps/admin/.env.local or Coolify build variables first.`);
  process.exit(1);
}
try {
  new URL(process.env.NEXT_PUBLIC_API_BASE_URL);
} catch {
  console.error("CMS build stopped: NEXT_PUBLIC_API_BASE_URL must be a valid absolute URL.");
  process.exit(1);
}
console.log("CMS public Firebase and API settings are configured.");
