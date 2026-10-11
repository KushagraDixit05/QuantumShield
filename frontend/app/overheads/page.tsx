import { OverheadsView } from "@/components/overheads/OverheadsView";
import { PageHeader } from "@/components/shared";

export default function Page() {
  return (
    <>
      <PageHeader kicker="Overheads" title="What the protection costs">
        Post-quantum signatures grow every update; the ZK proof costs minutes of proving on a laptop CPU. All figures are stored
        benchmark results, not measured when you open this page.
      </PageHeader>
      <OverheadsView />
    </>
  );
}
