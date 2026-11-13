"use client";
import { ArrowRight, Mail } from "lucide-react";
import { api } from "@/lib/api";
import { ROLE_LABELS } from "@/lib/types";
import { useMutation } from "@/lib/use-mutation";
import { Dialog } from "@/components/ui/dialog";
import { ErrorAlert } from "@/components/ui/feedback";
import { fields } from "@/components/ui/form";
import { useCompany } from "@/components/workspace/company-context";

export function InviteDialog({
  onClose,
  onDone,
}: {
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const { root, organization } = useCompany();
  const { busy, error, run } = useMutation();
  return (
    <Dialog title="Пригласить сотрудника" onClose={() => !busy && onClose()}>
      <p className="muted">
        Добавьте коллегу в компанию «{organization.name}».
      </p>
      <ErrorAlert message={error} />
      <form
        className="auth-form"
        onSubmit={(e) => {
          e.preventDefault();
          const data = fields(e.currentTarget);
          void run(async () => {
            const result = await api<{ message: string }>(
              `${root}/invitations`,
              data,
            );
            onDone(result.message);
          });
        }}
      >
        <label>
          Электронная почта
          <input
            autoFocus
            name="email"
            type="email"
            autoComplete="off"
            required
            maxLength={254}
            placeholder="colleague@company.kz"
          />
        </label>
        <label>
          Роль в компании
          <select name="role" defaultValue="manager">
            {organization.assignable_roles.map((role) => (
              <option key={role} value={role}>
                {ROLE_LABELS[role]}
              </option>
            ))}
          </select>
        </label>
        <p className="form-note">
          <Mail size={15} /> Приглашение действует 7 дней.
        </p>
        <button className="button primary full" disabled={busy}>
          {busy ? "Отправляем…" : "Отправить приглашение"}
          <ArrowRight size={16} />
        </button>
      </form>
    </Dialog>
  );
}
