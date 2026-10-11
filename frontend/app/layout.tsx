import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/shell/AppShell";

export const metadata: Metadata = {
  title: "QuantumShield-FL",
  description: "Post-quantum signed, ZK-checked federated learning: stored results, live runs, replayed proofs",
};

// Runs synchronously before first paint: apply a stored theme choice, else leave the
// prefers-color-scheme media query in CSS to decide. No flash, no hydration mismatch.
const themeInit = `try{var t=localStorage.getItem("qs-theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
