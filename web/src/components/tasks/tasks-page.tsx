"use client";
import { useState } from "react";
import Link from "next/link";
import { formatDateTime } from "@/lib/format";
import type { LeadRecord, Task } from "@/lib/types";
import { useInterval } from "@/lib/use-interval";
import { usePagedList } from "@/lib/use-paged-list";
import { ErrorAlert, LoadingState, LoadMore } from "@/components/ui/feedback";
import { PageHeading } from "@/components/ui/page-heading";
import { useCompany } from "@/components/workspace/company-context";
import { useSection } from "@/components/workspace/shell";
import { TaskItem } from "./task-item";

const FILTERS = [
  ["open", "Открытые"],
  ["overdue", "Просроченные"],
  ["today", "До конца дня"],
  ["completed", "Выполненные"],
  ["all", "Все задачи"],
];

function matches(task: Task, status: string) {
  if (status === "all") return true;
  if (status === "completed") return task.completed;
  if (task.completed) return false;
  return status === "overdue" ? task.overdue : true;
}

export function TasksPage() {
  const { root, base } = useCompany();
  const { item, eyebrow } = useSection();
  const [status, setStatus] = useState("open");
  const [editing, setEditing] = useState(false);
  const tasks = usePagedList<Task>(`${root}/tasks`, { status });
  const contacts = usePagedList<LeadRecord>(`${root}/contacts-due`);
  const refresh = () => {
    tasks.reload();
    contacts.reload();
  };
  // Напоминания обновляются раз в минуту, пока не редактируется форма.
  useInterval(
    refresh,
    editing || tasks.page > 1 || contacts.page > 1 ? null : 60000,
  );
  return (
    <>
      <PageHeading
        eyebrow={eyebrow}
        title={item?.label || "Задачи"}
        description={item?.description}
      />
      <div className="sales-toolbar">
        <label className="sr-only" htmlFor="task-status">
          Фильтр задач
        </label>
        <select
          id="task-status"
          value={status}
          onChange={(e) => {
            setEditing(false);
            setStatus(e.target.value);
          }}
        >
          {FILTERS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <span className="small muted">Задач: {tasks.total}</span>
        <button className="text-button" onClick={refresh}>
          Обновить
        </button>
      </div>
      <p className="sales-hint muted small">
        Задачи создаются в карточке обращения. Напоминания приходят и в
        уведомления, если они включены в настройках.
      </p>
      <ErrorAlert message={tasks.error || contacts.error} onRetry={refresh} />
      {tasks.loading && !tasks.items.length ? (
        <LoadingState text="Загружаем задачи…" />
      ) : !tasks.items.length ? (
        <div className="card empty-state">
          <h3>Задач по этому фильтру нет</h3>
          <p>Откройте обращение и добавьте следующий шаг.</p>
        </div>
      ) : (
        <div className="task-list">
          {tasks.items.map((task) => (
            <TaskItem
              key={`${task.id}-${task.version}`}
              task={task}
              root={root}
              leadHref={`${base}/leads/${task.lead_id}`}
              onEditing={setEditing}
              onSaved={(saved) => {
                // Строка обновляется на месте; если задача больше не подходит
                // под фильтр (выполнена в «Открытых»), она убирается из списка.
                tasks.setItems((items) =>
                  items
                    .map((t) => (t.id === saved.id ? saved : t))
                    .filter((t) => t.id !== saved.id || matches(t, status)),
                );
                contacts.reload();
              }}
            />
          ))}
        </div>
      )}
      <LoadMore
        visible={tasks.hasMore}
        loading={tasks.loading}
        onClick={tasks.loadMore}
        label="Загрузить ещё задачи"
      />
      <h2 className="sales-section">
        Пора связаться <span className="subtle-pill">{contacts.total}</span>
      </h2>
      <div className="card">
        {contacts.items.length ? (
          contacts.items.map((lead) => (
            <Link
              className="client-lead"
              key={lead.id}
              href={`${base}/leads/${lead.id}`}
            >
              <strong>
                {lead.client_name} · {lead.title}
              </strong>
              <span>{formatDateTime(lead.next_contact_at)}</span>
            </Link>
          ))
        ) : (
          <p className="muted small">
            Нет обращений с наступившим временем следующего контакта.
          </p>
        )}
      </div>
      <LoadMore
        visible={contacts.hasMore}
        loading={contacts.loading}
        onClick={contacts.loadMore}
        label="Загрузить ещё контакты"
      />
    </>
  );
}
