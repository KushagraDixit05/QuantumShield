"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  { href: "/", label: "Overview" },
  { href: "/run", label: "Run" },
  { href: "/zk", label: "ZK" },
  { href: "/consensus", label: "Consensus" },
  { href: "/overheads", label: "Overheads" },
  { href: "/attacks", label: "Attack matrix" },
  { href: "/limitations", label: "Limitations" },
];

export function Nav() {
  const path = usePathname();
  return (
    <nav className="qs-nav" aria-label="Primary">
      <div className="qs-brand">
        <b>QuantumShield</b>FL evidence console
      </div>
      {ITEMS.map((i) => {
        const active = i.href === "/" ? path === "/" : path.startsWith(i.href);
        return (
          <Link key={i.href} href={i.href} aria-current={active ? "page" : undefined}>
            {i.label}
          </Link>
        );
      })}
    </nav>
  );
}
