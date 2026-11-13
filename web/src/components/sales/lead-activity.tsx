"use client";
import { api } from "@/lib/api";
import { formatDateTime, fromLocalInput } from "@/lib/format";
import type { LeadRecord } from "@/lib/types";
import { useMutation } from "@/lib/use-mutation";
import { ErrorAlert } from "@/components/ui/feedback";
import { fields } from "@/components/ui/form";

/** Новая задача, комментарий и история обращения. */
export function LeadActivity({
  root,
  lead,
  onChanged,
}: {
  root: string;
  lead: LeadRecord;
  onChanged: () => void;
}) {
  const { busy, error, run } = useMutation(onChanged);
  const submit =
    (
      path: string,
      transform: (data: Record<string, unknown>) => Record<string, unknown>,
    ) =>
    (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const form = event.currentTarget;
      const data = fields(form);
      void run(async () => {
        await api(`${root}/leads/${lead.id}/${path}`, transform(data));
        form.reset();
      });
    };
  return (
    <>
      <ErrorAlert message={error} />
      <article className="card sales-section">
        <h3>Новая задача</h3>
        <p className="card-intro">
          Ответственный — {lead.assignee_name}. Все задачи доступны в разделе
          «Задачи».
        </p>
        <form
          className="auth-form"
          onSubmit={submit("tasks", (data) => ({
            title: data.title,
            due_at: fromLocalInput(data.due_at as string),
          }))}
        >
          <div className="form-grid">
            <label>
              Что нужно сделать
              <input
                name="title"
                required
                maxLength={240}
                placeholder="Например, перезвонить родственнику"
              />
            </label>
            <label>
              Срок
              <input name="due_at" type="datetime-local" required />
            </label>
          </div>
          <button className="button secondary" disabled={busy}>
            Добавить задачу
          </button>
        </form>
      </article>
      <article className="card sales-section">
        <h3>История и комментарии</h3>
        <form className="auth-form" onSubmit={submit("comments", (d) => d)}>
          <label>
            Комментарий
            <textarea name="text" required maxLength={5000} rows={3} />
          </label>
          <button className="button secondary" disabled={busy}>
            Добавить комментарий
          </button>
        </form>
        <div className="sales-history">
          {lead.activities?.map((a) => (
            <article key={a.id}>
              <strong>{a.actor}</strong>
              <time>{formatDateTime(a.created_at)}</time>
              <p>{a.text}</p>
            </article>
          ))}
        </div>
      </article>
    </>
  );
}
