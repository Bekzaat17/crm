"use client";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { ClientRecord } from "@/lib/types";
import { useMutation } from "@/lib/use-mutation";
import { Dialog } from "@/components/ui/dialog";
import { ErrorAlert } from "@/components/ui/feedback";
import { fields } from "@/components/ui/form";
import { useCompany } from "@/components/workspace/company-context";
import { ClientFields } from "./client-fields";

export function NewClientDialog({ onClose }: { onClose: () => void }) {
  const { root, base } = useCompany();
  const router = useRouter();
  const { busy, error, run } = useMutation();
  return (
    <Dialog title="Новый клиент" onClose={() => !busy && onClose()}>
      <ErrorAlert message={error} />
      <form
        className="auth-form"
        onSubmit={(e) => {
          e.preventDefault();
          const data = fields(e.currentTarget);
          void run(async () => {
            const client = await api<ClientRecord>(`${root}/clients`, data);
            router.push(`${base}/clients/${client.id}`);
          });
        }}
      >
        <ClientFields />
        <button className="button primary" disabled={busy}>
          Создать карточку
        </button>
      </form>
    </Dialog>
  );
}
