"use client";
import { Admission } from "@/components/integrations/admission";
import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import type { LeadRecord, Metadata } from "./types";
import { Dialog, fields } from "./forms";
import { useSalesMutation } from "./use-sales-mutation";
export function LeadEditor({
  initial,
  root,
  meta,
  onClose,
  onSaved,
  onOpenClient,
}: {
  initial: LeadRecord;
  root: string;
  meta: Metadata | null;
  onClose: () => void;
  onSaved: () => void;
  onOpenClient: (id: string) => void;
}) {
  const [selectedLead, setSelectedLead] = useState(initial);
  const { busy, error: formError, run: mutation } = useSalesMutation(onSaved);
  const close = () => {
    if (!busy) onClose();
  };
  const openClient = onOpenClient;
  const openLead = async (id: string) =>
    setSelectedLead(await api<LeadRecord>(`${root}/leads/${id}`));
  return (
    <Dialog title={selectedLead.title} onClose={close}>
      {formError && (
        <div className="alert error" role="alert">
          {formError}
        </div>
      )}
      <button
        className="text-button"
        onClick={() => {
          const id = selectedLead.client_id;
          void openClient(id);
        }}
      >
        Карточка: {selectedLead.client_name} <ArrowRight size={14} />
      </button>
      <form
        className="auth-form sales-section"
        key={selectedLead.version}
        onSubmit={(e) => {
          e.preventDefault();
          const data = fields(e.currentTarget);
          const raw = String(data.next_contact_at || "");
          void mutation(async () =>
            setSelectedLead(
              await api<LeadRecord>(`${root}/leads/${selectedLead.id}`, {
                ...data,
                version: selectedLead.version,
                next_contact_at: raw ? new Date(raw).toISOString() : "",
              }),
            ),
          );
        }}
      >
        <label>
          Название
          <input
            name="title"
            required
            maxLength={240}
            defaultValue={selectedLead.title}
          />
        </label>
        <label>
          Источник
          <input
            name="source"
            maxLength={120}
            defaultValue={selectedLead.source}
          />
        </label>
        <label>
          Этап
          <select name="stage" defaultValue={selectedLead.stage}>
            {meta?.stages.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Причина отказа (обязательна для этапа «Отказ»)
          <textarea
            name="refusal_reason"
            maxLength={500}
            defaultValue={selectedLead.refusal_reason}
          />
        </label>
        <label>
          Ответственный
          <select
            name="assignee_id"
            defaultValue={selectedLead.assignee_id}
            disabled={!meta?.can_assign}
          >
            {!meta?.assignees.some(
              (a) => a.id === selectedLead.assignee_id,
            ) && (
              <option value={selectedLead.assignee_id}>
                {selectedLead.assignee_name} (доступ отключён)
              </option>
            )}
            {meta?.assignees.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Следующий контакт (ваше местное время)
          <input
            name="next_contact_at"
            type="datetime-local"
            defaultValue={
              selectedLead.next_contact_at
                ? (() => {
                    const d = new Date(selectedLead.next_contact_at);
                    return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
                      .toISOString()
                      .slice(0, 16);
                  })()
                : ""
            }
          />
        </label>
        <p className="small muted">
          «Поступил» фиксирует факт в CRM. Передача в RehubPro ещё не
          подключена.
        </p>
        <button className="button primary" disabled={busy}>
          Сохранить изменения
        </button>
      </form>
      <Admission
        root={root}
        lead={selectedLead}
        canSend={meta?.can_send || false}
        onSaved={onSaved}
      />
      <h3 className="sales-section">Новая задача</h3>
      <p className="small muted">
        Ответственный — {selectedLead.assignee_name}. Все задачи доступны в
        разделе «Задачи».
      </p>
      <form
        className="auth-form sales-section"
        onSubmit={(event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const data = fields(form);
          void mutation(async () => {
            await api(`${root}/leads/${selectedLead.id}/tasks`, {
              title: data.title,
              due_at: new Date(String(data.due_at)).toISOString(),
            });
            form.reset();
            await openLead(selectedLead.id);
          });
        }}
      >
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
          Срок (ваше местное время)
          <input name="due_at" type="datetime-local" required />
        </label>
        <button className="button secondary" disabled={busy}>
          Добавить задачу
        </button>
      </form>
      <h3 className="sales-section">История и комментарии</h3>
      <form
        className="auth-form"
        onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget,
            data = fields(form);
          void mutation(async () => {
            await api(`${root}/leads/${selectedLead.id}/comments`, data);
            form.reset();
            await openLead(selectedLead.id);
          });
        }}
      >
        <label>
          Комментарий
          <textarea name="text" required maxLength={5000} rows={3} />
        </label>
        <button className="button secondary" disabled={busy}>
          Добавить комментарий
        </button>
      </form>
      <div className="sales-history">
        {selectedLead.activities?.map((a) => (
          <article key={a.id}>
            <strong>{a.actor}</strong>
            <time>{new Date(a.created_at).toLocaleString("ru")}</time>
            <p>{a.text}</p>
          </article>
        ))}
      </div>
    </Dialog>
  );
}
