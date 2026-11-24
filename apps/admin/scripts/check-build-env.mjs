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
  "NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID",
];
const missing = required.filter((key) => !process.env[key]?.trim());
if (missing.length) {
  console.error(`[check-build-env] Configure required deployment values: ${missing.join(", ")}`);
  process.exit(1);
}

try {
  const apiUrl = new URL(process.env.NEXT_PUBLIC_API_BASE_URL);
  const httpSslipTest =
    process.env.ALLOW_HTTP_TEST_API?.trim().toLowerCase() === "true" &&
    apiUrl.protocol === "http:" &&
    apiUrl.hostname.endsWith(".sslip.io");
  if (apiUrl.protocol !== "https:" && !httpSslipTest) {
    throw new Error("API URL must use HTTPS, except for explicitly enabled sslip.io testing.");
  }
} catch {
  console.error("[check-build-env] NEXT_PUBLIC_API_BASE_URL must be HTTPS. HTTP is allowed only for an explicitly enabled sslip.io test domain.");
  process.exit(1);
}

console.log("CMS deployment configuration is present.");
