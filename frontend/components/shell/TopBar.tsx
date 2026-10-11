import { HealthIndicator } from "./HealthIndicator";
import { ThemeToggle } from "./ThemeToggle";

export function TopBar() {
  return (
    <header className="qs-top">
      <span className="qs-chip zk" title="Proofs are read from stored receipts; this server never proves live">
        ZK: replay only
      </span>
      <HealthIndicator />
      <span className="spacer" />
      <ThemeToggle />
    </header>
  );
}
