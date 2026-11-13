"use client";
import Link from "next/link";
import { api } from "@/lib/api";
import { fromLocalInput, toLocalInput } from "@/lib/format";
import type { Task } from "@/lib/types";
import { useMutation } from "@/lib/use-mutation";
import { ErrorAlert } from "@/components/ui/feedback";
import { fields } from "@/components/ui/form";

export function TaskItem({
  task,
  root,
  leadHref,
  onEditing,
  onSaved,
}: {
  task: Task;
  root: string;
  leadHref: string;
  onEditing: (editing: boolean) => void;
  onSaved: (task: Task) => void;
}) {
  const { busy, error, run } = useMutation();
  const update = (data: Record<string, unknown>) =>
    run(async () => {
      const saved = await api<Task>(`${root}/tasks/${task.id}`, {
        ...data,
        version: task.version,
      });
      onEditing(false);
      onSaved(saved);
    });
  return (
    <article className={`card task-item ${task.overdue ? "task-overdue" : ""}`}>
      <div className="section-title">
        <span className="subtle-pill">
          {task.completed
            ? "Выполнена"
            : task.overdue
              ? "Просрочена"
              : "Запланирована"}
        </span>
        <span className="small muted">{task.assignee_name}</span>
      </div>
      <Link className="text-button task-lead" href={leadHref}>
        {task.client_name} · {task.lead_title}
      </Link>
      <ErrorAlert message={error} />
      <form
        className="auth-form"
        onChange={() => onEditing(true)}
        onSubmit={(e) => {
          e.preventDefault();
          const data = fields(e.currentTarget);
          void update({ ...data, due_at: fromLocalInput(data.due_at) });
        }}
      >
        <label>
          Задача
          <input
            name="title"
            required
            maxLength={240}
            defaultValue={task.title}
          />
        </label>
        <label>
          Срок
          <input
            name="due_at"
            type="datetime-local"
            required
            defaultValue={toLocalInput(task.due_at)}
          />
        </label>
        <div className="task-actions">
          <button className="button secondary" disabled={busy}>
            Сохранить
          </button>
          <button
            type="button"
            className="button primary"
            disabled={busy}
            onClick={() => void update({ completed: !task.completed })}
          >
            {task.completed ? "Вернуть в работу" : "Выполнить"}
          </button>
        </div>
      </form>
    </article>
  );
}
