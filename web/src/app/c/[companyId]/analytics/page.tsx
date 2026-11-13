import { Suspense } from "react";
import { AnalyticsPage } from "@/components/analytics/analytics-page";
import { LoadingState } from "@/components/ui/feedback";

export default function Analytics() {
  return (
    <Suspense fallback={<LoadingState />}>
      <AnalyticsPage />
    </Suspense>
  );
}
