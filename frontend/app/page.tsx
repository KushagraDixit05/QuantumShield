import { OverviewView } from "@/components/overview/OverviewView";
import { PageHeader } from "@/components/shared";

export default function Page() {
  return (
    <>
      <PageHeader kicker="Overview" title="Does the defence hold?">
        Three stored scenarios: A is benign training, B is a scaled-update attack with no defence, C is the same attack with the hybrid
        signature check and plaintext norm gate. Every number below is read from the repository&apos;s result files through the backend.
      </PageHeader>
      <OverviewView />
    </>
  );
}
