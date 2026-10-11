import type { ReactNode } from "react";
import { Nav } from "./Nav";
import { TopBar } from "./TopBar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="qs-shell">
      <Nav />
      <div className="qs-main">
        <TopBar />
        <main className="qs-content">{children}</main>
      </div>
    </div>
  );
}
