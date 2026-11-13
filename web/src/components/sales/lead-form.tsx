"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { fromLocalInput, toLocalInput } from "@/lib/format";
import type { LeadRecord, PipelineMeta } from "@/lib/types";
import { useMutation } from "@/lib/use-mutation";
import { ErrorAlert } from "@/components/ui/feedback";
import { fields } from "@/components/ui/form";

export function LeadForm({
  root,
  lead,
  meta,
  onSaved,
}: {
  root: string;
  lead: LeadRecord;
  meta: PipelineMeta;
  onSaved: () => void;
}) {
  const { busy, error, run } = useMutation();
  const [stageId, setStageId] = useState(lead.stage);
  const stages = meta.stages.some((s) => s.id === lead.stage)
    ? meta.stages
    : [
        {
          id: lead.stage,
          name: `${lead.stage_label} (архив)`,
          kind: lead.stage_kind,
        },
        ...meta.stages,
      ];
  const refused = stages.find((s) => s.id === stageId)?.kind === "refused";
  return (
    <form
      className="auth-form card sales-section"
      onSubmit={(e) => {
        e.preventDefault();
        const data = fields(e.currentTarget);
        void run(async () => {
          await api<LeadRecord>(`${root}/leads/${lead.id}`, {
            ...data,
            version: lead.version,
            next_contact_at: fromLocalInput(data.next_contact_at),
          });
          onSaved();
        });
      }}
    >
      <ErrorAlert message={error} />
      <label>
        Название
        <input
          name="title"
          required
          maxLength={240}
          defaultValue={lead.title}
        />
      </label>
      <div className="form-grid">
        <label>
          Этап
          <select
            name="stage"
            value={stageId}
            onChange={(e) => setStageId(e.target.value)}
          >
            {stages.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Источник
          <input name="source" maxLength={120} defaultValue={lead.source} />
        </label>
      </div>
      {refused && (
        <label>
          Причина отказа
          <textarea
            name="refusal_reason"
            required
            maxLength={500}
            defaultValue={lead.refusal_reason}
          />
        </label>
      )}
      <div className="form-grid">
        <label>
          Ответственный
          <select
            name="assignee_id"
            defaultValue={lead.assignee_id}
            disabled={!meta.can_assign}
          >
            {!meta.assignees.some((a) => a.id === lead.assignee_id) && (
              <option value={lead.assignee_id}>
                {lead.assignee_name} (доступ отключён)
              </option>
            )}
            {meta.assignees.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Следующий контакт
          <input
            name="next_contact_at"
            type="datetime-local"
            defaultValue={toLocalInput(lead.next_contact_at)}
          />
        </label>
      </div>
      <p className="small muted">
        Этап с типом «Поступил» фиксирует факт в CRM. Передача резидента в
        RehubPro подтверждается отдельно ниже.
      </p>
      <button className="button primary" disabled={busy}>
        Сохранить изменения
      </button>
    </form>
  );
}
