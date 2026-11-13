"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, errorMessage } from "@/lib/api";
import type { ClientRecord, LeadRecord, Page, PipelineMeta } from "@/lib/types";
import { useMutation } from "@/lib/use-mutation";
import { Dialog } from "@/components/ui/dialog";
import { ErrorAlert } from "@/components/ui/feedback";
import { fields } from "@/components/ui/form";
import { useCompany } from "@/components/workspace/company-context";

type Suggestion = Pick<ClientRecord, "id" | "name" | "phone">;

export function NewLeadDialog({
  meta,
  client,
  onClose,
}: {
  meta: PipelineMeta;
  client?: Suggestion;
  onClose: () => void;
}) {
  const { root, base } = useCompany();
  const router = useRouter();
  const { busy, error, setError, run } = useMutation();
  const [search, setSearch] = useState(client?.name || "");
  const [suggestions, setSuggestions] = useState<Suggestion[]>(
    client ? [client] : [],
  );
  useEffect(() => {
    if (client && search === client.name) return;
    let active = true;
    const timer = setTimeout(() => {
      api<Page<ClientRecord>>(`${root}/clients?q=${encodeURIComponent(search)}`)
        .then((result) => active && setSuggestions(result.items))
        .catch((cause) => active && setError(errorMessage(cause)));
    }, 200);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [root, search, client, setError]);
  return (
    <Dialog title="Новое обращение" onClose={() => !busy && onClose()}>
      <ErrorAlert message={error} />
      <form
        className="auth-form"
        onSubmit={(e) => {
          e.preventDefault();
          const data = fields(e.currentTarget);
          void run(async () => {
            const lead = await api<LeadRecord>(`${root}/leads`, data);
            router.push(`${base}/leads/${lead.id}`);
          });
        }}
      >
        <label>
          Найти клиента
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Имя или телефон"
          />
        </label>
        <label>
          Клиент
          <select
            name="client_id"
            required
            defaultValue={client?.id || ""}
            key={suggestions.map((c) => c.id).join()}
          >
            <option value="">Выберите клиента</option>
            {suggestions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} {c.phone}
              </option>
            ))}
          </select>
        </label>
        <p className="small muted">
          Если клиента ещё нет, сначала создайте карточку в разделе «Клиенты».
        </p>
        <label>
          Название обращения
          <input
            name="title"
            required
            maxLength={240}
            placeholder="Например, первичная консультация"
          />
        </label>
        <label>
          Источник
          <input
            name="source"
            maxLength={120}
            placeholder="Сайт, звонок, рекомендация…"
          />
        </label>
        <div className="form-grid">
          <label>
            Ответственный
            <select name="assignee_id" required>
              {meta.assignees.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Филиал
            <select name="branch_id" required>
              {meta.branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button className="button primary" disabled={busy}>
          Создать обращение
        </button>
      </form>
    </Dialog>
  );
}
