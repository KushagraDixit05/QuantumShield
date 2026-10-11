import { PageHeader } from "@/components/shared";
import { ZkView } from "@/components/zk/ZkView";

export default function Page() {
  return (
    <>
      <PageHeader kicker="Zero-knowledge" title="Proof receipts (replayed)">
        Stored RISC Zero receipts and what the verifier says about them. No proof is generated from this page.
      </PageHeader>
      <ZkView />
    </>
  );
}
