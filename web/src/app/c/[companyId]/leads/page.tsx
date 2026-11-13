import { Suspense } from "react";
import { LeadsBoard } from "@/components/sales/leads-board";
import { LoadingState } from "@/components/ui/feedback";

export default function LeadsPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <LeadsBoard />
    </Suspense>
  );
}
