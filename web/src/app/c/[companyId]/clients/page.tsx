import { Suspense } from "react";
import { ClientsList } from "@/components/sales/clients-list";
import { LoadingState } from "@/components/ui/feedback";

export default function ClientsPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <ClientsList />
    </Suspense>
  );
}
