import { AttackHeatmap } from "@/components/heatmap/AttackHeatmap";
import { PageHeader } from "@/components/shared";

export default function Page() {
  return (
    <>
      <PageHeader kicker="Attack matrix" title="What each defence actually did">
        Measured outcomes for every attack and defence pairing, including the cells where the attack was not stopped or the run diverged.
      </PageHeader>
      <AttackHeatmap />
    </>
  );
}
