"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Branch } from "@/lib/types";
import { useMutation } from "@/lib/use-mutation";
import { useResource } from "@/lib/use-resource";
import { ErrorAlert, LoadingState } from "@/components/ui/feedback";
import { fields } from "@/components/ui/form";
import { useCompany } from "@/components/workspace/company-context";

function BranchRow({
  branch,
  path,
  onSaved,
}: {
  branch: Branch;
  path: string;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const { busy, error, run } = useMutation(() => {
    setEditing(false);
    onSaved();
  });
  return (
    <div className={`settings-row ${branch.is_active ? "" : "archived"}`}>
      {editing ? (
        <form
          className="inline-form"
          onSubmit={(e) => {
            e.preventDefault();
            const data = fields(e.currentTarget);
            void run(() => api(path, { ...data, version: branch.version }));
          }}
        >
          <label className="sr-only" htmlFor={`branch-${branch.id}`}>
            Название филиала
          </label>
          <input
            id={`branch-${branch.id}`}
            name="name"
            required
            maxLength={160}
            defaultValue={branch.name}
          />
          <button className="button primary" disabled={busy}>
            Сохранить
          </button>
          <button
            type="button"
            className="button secondary"
            onClick={() => setEditing(false)}
          >
            Отмена
          </button>
        </form>
      ) : (
        <>
          <strong>{branch.name}</strong>
          {!branch.is_active && <span className="subtle-pill">В архиве</span>}
          <div className="row-actions">
            {branch.is_active && (
              <button className="text-button" onClick={() => setEditing(true)}>
                Переименовать
              </button>
            )}
            <button
              className="text-button"
              disabled={busy}
              onClick={() =>
                void run(() =>
                  api(
                    `${path}/${branch.is_active ? "archive" : "restore"}`,
                    {},
                  ),
                )
              }
            >
              {branch.is_active ? "В архив" : "Восстановить"}
            </button>
          </div>
        </>
      )}
      <ErrorAlert message={error} />
    </div>
  );
}

export function BranchSettings() {
  const { root, can, reload: reloadCompany } = useCompany();
  const manage = can("manage_branches");
  const branches = useResource<{ items: Branch[] }>(
    `${root}/branches${manage ? "?archived=1" : ""}`,
  );
  const refresh = () => {
    branches.reload();
    reloadCompany();
  };
  const create = useMutation(refresh);
  return (
    <article className="card">
      <div className="section-title">
        <h2>Филиалы</h2>
      </div>
      <p className="small muted">
        Обращение относится к одному действующему филиалу. Филиал с обращениями
        не удаляется — его можно отправить в архив.
      </p>
      <ErrorAlert message={branches.error} onRetry={branches.reload} />
      {!branches.data ? (
        <LoadingState />
      ) : (
        branches.data.items.map((branch) =>
          manage ? (
            <BranchRow
              key={`${branch.id}-${branch.version}`}
              branch={branch}
              path={`${root}/branches/${branch.id}`}
              onSaved={refresh}
            />
          ) : (
            <div className="settings-row" key={branch.id}>
              <strong>{branch.name}</strong>
            </div>
          ),
        )
      )}
      {manage && (
        <form
          className="inline-form sales-section"
          onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const data = fields(form);
            void create.run(async () => {
              await api(`${root}/branches`, data);
              form.reset();
            });
          }}
        >
          <label className="sr-only" htmlFor="new-branch">
            Название нового филиала
          </label>
          <input
            id="new-branch"
            name="name"
            required
            maxLength={160}
            placeholder="Название нового филиала"
          />
          <button className="button primary" disabled={create.busy}>
            Добавить филиал
          </button>
        </form>
      )}
      <ErrorAlert message={create.error} />
    </article>
  );
}
