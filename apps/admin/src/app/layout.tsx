import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EnerTech Admin | Customer Platform",
  description: "EnerTech customer platform content and operations workspace.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="enertech">
      <body>{children}</body>
    </html>
  );
}
