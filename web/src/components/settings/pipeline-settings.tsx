"use client";
import { useState } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { api } from "@/lib/api";
import type { Stage, StageKind } from "@/lib/types";
import { useMutation } from "@/lib/use-mutation";
import { useResource } from "@/lib/use-resource";
import { Dialog } from "@/components/ui/dialog";
import { ErrorAlert, LoadingState, Notice } from "@/components/ui/feedback";
import { fields } from "@/components/ui/form";
import { useCompany } from "@/components/workspace/company-context";

const KINDS: { value: StageKind; label: string; hint: string }[] = [
  { value: "open", label: "В работе", hint: "Обращение ещё не закрыто" },
  { value: "admitted", label: "Поступил", hint: "Клиент поступил в центр" },
  { value: "refused", label: "Отказ", hint: "Требует причину отказа" },
];

function KindSelect({
  value,
  disabled,
  label = "Тип этапа",
}: {
  value: StageKind;
  disabled?: boolean;
  label?: string;
}) {
  return (
    <select
      name="kind"
      defaultValue={value}
      disabled={disabled}
      aria-label={label}
    >
      {KINDS.map((k) => (
        <option key={k.value} value={k.value} title={k.hint}>
          {k.label}
        </option>
      ))}
    </select>
  );
}

function ArchiveDialog({
  stage,
  stages,
  root,
  onClose,
  onDone,
}: {
  stage: Stage;
  stages: Stage[];
  root: string;
  onClose: () => void;
  onDone: (moved: number) => void;
}) {
  const { busy, error, run } = useMutation();
  const targets = stages.filter(
    (s) => s.is_active && s.id !== stage.id && s.kind === stage.kind,
  );
  return (
    <Dialog
      title={`Архивировать «${stage.name}»`}
      onClose={() => !busy && onClose()}
    >
      <ErrorAlert message={error} />
      <form
        className="auth-form"
        onSubmit={(e) => {
          e.preventDefault();
          const data = fields(e.currentTarget);
          void run(async () => {
            const result = await api<{ moved_leads: number }>(
              `${root}/stages/${stage.id}/archive`,
              data,
            );
            onDone(result.moved_leads);
          });
        }}
      >
        {stage.lead_count && !targets.length ? (
          <p className="alert error">
            Нет другого активного этапа типа «{stage.kind_label}». Сначала
            создайте его, чтобы перенести обращения.
          </p>
        ) : stage.lead_count ? (
          <label>
            Перенести обращения ({stage.lead_count}) в этап
            <select name="move_to" required>
              {targets.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <p className="muted">В этапе нет обращений.</p>
        )}
        <p className="small muted">
          Обращения можно перенести только в этап того же типа. Перенос
          записывается в историю каждого обращения.
        </p>
        <button
          className="button danger"
          disabled={busy || Boolean(stage.lead_count && !targets.length)}
        >
          Архивировать
        </button>
      </form>
    </Dialog>
  );
}

function StageRow({
  stage,
  root,
  first,
  last,
  busy,
  onMove,
  onArchive,
  onSaved,
}: {
  stage: Stage;
  root: string;
  first: boolean;
  last: boolean;
  busy: boolean;
  onMove: (direction: -1 | 1) => void;
  onArchive: () => void;
  onSaved: () => void;
}) {
  const save = useMutation(onSaved);
  return (
    <div className="settings-row stage-row">
      <div className="row-actions">
        <button
          className="icon-button"
          aria-label={`Поднять этап ${stage.name}`}
          disabled={first || busy}
          onClick={() => onMove(-1)}
        >
          <ArrowUp size={15} />
        </button>
        <button
          className="icon-button"
          aria-label={`Опустить этап ${stage.name}`}
          disabled={last || busy}
          onClick={() => onMove(1)}
        >
          <ArrowDown size={15} />
        </button>
      </div>
      <form
        className="stage-form"
        onSubmit={(e) => {
          e.preventDefault();
          const data = fields(e.currentTarget);
          void save.run(() =>
            api(`${root}/stages/${stage.id}`, {
              ...data,
              version: stage.version,
            }),
          );
        }}
      >
        <input
          type="color"
          name="color"
          defaultValue={stage.color || "#64748b"}
          aria-label={`Цвет этапа ${stage.name}`}
        />
        <input
          name="name"
          required
          maxLength={80}
          defaultValue={stage.name}
          aria-label={`Название этапа ${stage.name}`}
        />
        <KindSelect
          value={stage.kind}
          disabled={Boolean(stage.lead_count)}
          label={`Тип этапа ${stage.name}`}
        />
        <span className="stage-count">Обращений: {stage.lead_count || 0}</span>
        <button className="button secondary" disabled={save.busy}>
          Сохранить
        </button>
        <button
          type="button"
          className="text-button danger-text"
          onClick={onArchive}
        >
          В архив
        </button>
      </form>
      <ErrorAlert message={save.error} />
    </div>
  );
}

export function PipelineSettings() {
  const { root } = useCompany();
  const stages = useResource<{ items: Stage[] }>(`${root}/stages`);
  const [archiving, setArchiving] = useState<Stage | null>(null);
  const [notice, setNotice] = useState("");
  const action = useMutation(stages.reload);
  const items = stages.data?.items || [];
  const active = items.filter((s) => s.is_active);
  const archived = items.filter((s) => !s.is_active);

  const move = (index: number, direction: -1 | 1) => {
    const ids = active.map((s) => s.id);
    [ids[index], ids[index + direction]] = [ids[index + direction], ids[index]];
    void action.run(() => api(`${root}/stages/reorder`, { ids }));
  };

  return (
    <article className="card">
      <div className="section-title">
        <h2>Этапы воронки</h2>
      </div>
      <p className="card-intro">
        Название и порядок этапов задаёт компания. Тип определяет правила: «В
        работе» — открытое обращение с напоминаниями, «Поступил» — поступление,
        «Отказ» — требует причину. Тип этапа с обращениями изменить нельзя.
      </p>
      <Notice message={notice} onClose={() => setNotice("")} />
      <ErrorAlert
        message={stages.error || action.error}
        onRetry={stages.reload}
      />
      {!stages.data ? (
        <LoadingState />
      ) : (
        <>
          {active.map((stage, index) => (
            <StageRow
              key={`${stage.id}-${stage.version}`}
              stage={stage}
              root={root}
              first={index === 0}
              last={index === active.length - 1}
              busy={action.busy}
              onMove={(direction) => move(index, direction)}
              onArchive={() => setArchiving(stage)}
              onSaved={stages.reload}
            />
          ))}
          <div className="settings-row stage-row stage-new">
            <span className="stage-new-label">Новый этап</span>
            <form
              className="stage-form"
              onSubmit={(e) => {
                e.preventDefault();
                const form = e.currentTarget;
                const data = fields(form);
                void action.run(async () => {
                  await api(`${root}/stages`, data);
                  form.reset();
                });
              }}
            >
              <input
                type="color"
                name="color"
                defaultValue="#2563eb"
                aria-label="Цвет этапа"
              />
              <input
                name="name"
                required
                maxLength={80}
                placeholder="Например, консультация прошла"
                aria-label="Название нового этапа"
              />
              <KindSelect value="open" />
              <button
                className="button primary stage-add"
                disabled={action.busy}
              >
                Добавить этап
              </button>
            </form>
          </div>
          {archived.length > 0 && (
            <>
              <h3 className="sales-section">Архив</h3>
              {archived.map((stage) => (
                <div className="settings-row archived" key={stage.id}>
                  <strong>{stage.name}</strong>
                  <span className="subtle-pill">{stage.kind_label}</span>
                  <button
                    className="text-button"
                    disabled={action.busy}
                    onClick={() =>
                      void action.run(() =>
                        api(`${root}/stages/${stage.id}/restore`, {}),
                      )
                    }
                  >
                    Восстановить
                  </button>
                </div>
              ))}
            </>
          )}
        </>
      )}
      {archiving && (
        <ArchiveDialog
          stage={archiving}
          stages={items}
          root={root}
          onClose={() => setArchiving(null)}
          onDone={(moved) => {
            setArchiving(null);
            setNotice(
              moved
                ? `Этап архивирован, обращений перенесено: ${moved}.`
                : "Этап архивирован.",
            );
            stages.reload();
          }}
        />
      )}
    </article>
  );
}
