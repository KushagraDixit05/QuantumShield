import { RunView } from "@/components/scenario/RunView";
import { PageHeader } from "@/components/shared";

export default function Page() {
  return (
    <>
      <PageHeader kicker="Scenario runner" title="Run a scenario">
        Start a federated-learning run on the backend and watch it round by round. Everything below the Run button is computed live by the backend
        for this session; ZK is never run live.
      </PageHeader>
      <RunView />
    </>
  );
}
