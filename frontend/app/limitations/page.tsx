import { LimitationsView } from "@/components/LimitationsView";
import { PageHeader } from "@/components/shared";

export default function Page() {
  return (
    <>
      <PageHeader kicker="Limitations" title="What this MVP does not prove">
        Each item constrains the claim. The list is parsed from the repository&apos;s limitations file, not retyped here.
      </PageHeader>
      <LimitationsView />
    </>
  );
}
