"use client";
import { api } from "@/lib/api";
import type { Member } from "@/lib/types";
import { useMutation } from "@/lib/use-mutation";
import { Dialog } from "@/components/ui/dialog";
import { ErrorAlert } from "@/components/ui/feedback";
import { fields } from "@/components/ui/form";
import { useCompany } from "@/components/workspace/company-context";

/** Передача владения: новый владелец — активный сотрудник, вы станете администратором. */
export function OwnershipDialog({
  members,
  onClose,
  onDone,
}: {
  members: Member[];
  onClose: () => void;
  onDone: () => void;
}) {
  const { root, session } = useCompany();
  const { busy, error, run } = useMutation(onDone);
  const candidates = members.filter(
    (m) => m.is_active && m.user_id !== session.user?.id,
  );
  return (
    <Dialog title="Передать владение" onClose={() => !busy && onClose()}>
      <p className="muted">
        Новый владелец получит полный доступ, включая передачу владения. Вы
        станете администратором компании.
      </p>
      <ErrorAlert message={error} />
      {candidates.length ? (
        <form
          className="auth-form"
          onSubmit={(e) => {
            e.preventDefault();
            const data = fields(e.currentTarget);
            void run(() => api(`${root}/ownership`, data));
          }}
        >
          <label>
            Новый владелец
            <select name="membership_id" required>
              {candidates.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} · {m.role_label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Ваш пароль
            <input
              name="password"
              type="password"
              required
              autoComplete="current-password"
            />
          </label>
          <button className="button danger" disabled={busy}>
            {busy ? "Подождите…" : "Передать владение"}
          </button>
        </form>
      ) : (
        <p className="small muted">
          Сначала пригласите сотрудника: владение передаётся только активному
          участнику компании.
        </p>
      )}
    </Dialog>
  );
}
