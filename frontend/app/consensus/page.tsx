import { ConsensusView } from "@/components/consensus/ConsensusView";
import { PageHeader } from "@/components/shared";

export default function Page() {
  return (
    <>
      <PageHeader kicker="Consensus" title="Votes and certificates">
        Four simulated nodes, one fixed leader, a quorum of three. Pick a run to see how each round was voted on and finalized.
      </PageHeader>
      <ConsensusView />
    </>
  );
}
