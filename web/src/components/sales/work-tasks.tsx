"use client";
import { useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { LeadEditor } from "./lead-editor";
import type { LeadRecord, Metadata, List } from "./types";
import { fields } from "./forms";

type Task = {
  id: string;
  title: string;
  lead_id: string;
  lead_title: string;
  client_name: string;
  assignee_name: string;
  due_at: string;
  completed: boolean;
  overdue: boolean;
  version: number;
};
const localDate = (value: string) => {
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};
export function WorkTasks({
  companyId,
  onOpenClient,
}: {
  companyId: string;
  onOpenClient: (id: string) => void;
}) {
  const root = `organizations/${companyId}`;
  const [editing, setEditing] = useState(false);
  const [tasks, setTasks] = useState<Task[]>([]),
    [contacts, setContacts] = useState<LeadRecord[]>([]),
    [status, setStatus] = useState("open"),
    [page, setPage] = useState(1),
    [more, setMore] = useState(false),
    [total, setTotal] = useState(0),
    [contactsTotal, setContactsTotal] = useState(0),
    [contactPage, setContactPage] = useState(1),
    [contactMore, setContactMore] = useState(false);
  const [error, setError] = useState(""),
    [revision, setRevision] = useState(0),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true);
  const [lead, setLead] = useState<LeadRecord | null>(null),
    [meta, setMeta] = useState<Metadata | null>(null);
  const refresh = () => {
    setPage(1);
    setContactPage(1);
    setRevision((v) => v + 1);
  };
  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      try {
        const [taskData, contactData] = await Promise.all([
          api<List<Task>>(`${root}/tasks?status=${status}&page=${page}`),
          api<List<LeadRecord>>(`${root}/contacts-due?page=${contactPage}`),
        ]);
        if (!active) return;
        setTasks((old) =>
          page === 1
            ? taskData.items
            : [
                ...old,
                ...taskData.items.filter(
                  (item) => !old.some((row) => row.id === item.id),
                ),
              ],
        );
        setMore(taskData.has_more);
        setTotal(taskData.total);
        setContacts((old) =>
          contactPage === 1
            ? contactData.items
            : [
                ...old,
                ...contactData.items.filter(
                  (item) => !old.some((row) => row.id === item.id),
                ),
              ],
        );
        setContactsTotal(contactData.total);
        setContactMore(contactData.has_more);
        setError("");
      } catch (cause) {
        if (active) setError(errorMessage(cause));
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [root, status, page, contactPage, revision]);
  // На первой странице обновляем напоминания автоматически, не сбрасывая редактируемые поля.
  useEffect(() => {
    const timer = setInterval(() => {
      if (!editing && !busy && !lead && page === 1 && contactPage === 1)
        setRevision((v) => v + 1);
    }, 60000);
    return () => clearInterval(timer);
  }, [editing, busy, lead, page, contactPage]);
  async function openLead(id: string) {
    try {
      const [record, metadata] = await Promise.all([
        api<LeadRecord>(`${root}/leads/${id}`),
        api<Metadata>(`${root}/pipeline`),
      ]);
      setLead(record);
      setMeta(metadata);
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }
  async function update(task: Task, data: Record<string, unknown>) {
    setBusy(true);
    setError("");
    try {
      await api(`${root}/tasks/${task.id}`, { ...data, version: task.version });
      setEditing(false);
      refresh();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section>
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
            setPage(1);
          }}
        >
          <option value="open">Открытые</option>
          <option value="overdue">Просроченные</option>
          <option value="today">До конца дня</option>
          <option value="completed">Выполненные</option>
          <option value="all">Все задачи</option>
        </select>
        <span className="small muted">Задач: {total}</span>
        <button className="text-button" onClick={refresh}>
          Обновить
        </button>
      </div>
      <p className="sales-hint muted small">
        Создавайте задачи в карточке обращения. Ответственный за задачу —
        ответственный за обращение. Напоминания обновляются каждую минуту, пока
        CRM открыта.
      </p>
      {error && (
        <div className="alert error" role="alert">
          {error}
        </div>
      )}
      {loading && !tasks.length ? (
        <div className="loading-state">Загружаем задачи…</div>
      ) : !tasks.length ? (
        <div className="card empty-state">
          <h3>Задач по этому фильтру нет</h3>
          <p>Откройте обращение и добавьте следующий шаг.</p>
        </div>
      ) : (
        <div className="task-list" onChange={() => setEditing(true)}>
          {tasks.map((task) => (
            <article
              className={`card task-item ${task.overdue ? "task-overdue" : ""}`}
              key={`${task.id}-${task.version}`}
            >
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
              <button
                className="text-button task-lead"
                onClick={() => openLead(task.lead_id)}
              >
                {task.client_name} · {task.lead_title}
              </button>
              <form
                className="auth-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  const data = fields(e.currentTarget);
                  void update(task, {
                    ...data,
                    due_at: new Date(String(data.due_at)).toISOString(),
                  });
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
                  Срок (ваше местное время)
                  <input
                    name="due_at"
                    type="datetime-local"
                    required
                    defaultValue={localDate(task.due_at)}
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
                    onClick={() => update(task, { completed: !task.completed })}
                  >
                    {task.completed ? "Вернуть в работу" : "Выполнить"}
                  </button>
                </div>
              </form>
            </article>
          ))}
        </div>
      )}
      {more && (
        <button
          className="button secondary load-more"
          disabled={loading}
          onClick={() => setPage((v) => v + 1)}
        >
          Загрузить ещё задачи
        </button>
      )}
      <h2 className="sales-section">
        Пора связаться <span className="subtle-pill">{contactsTotal}</span>
      </h2>
      <div className="card">
        {contacts.length ? (
          contacts.map((contact) => (
            <button
              className="client-lead"
              key={contact.id}
              onClick={() => openLead(contact.id)}
            >
              <strong>
                {contact.client_name} · {contact.title}
              </strong>
              <span>
                {new Date(contact.next_contact_at).toLocaleString("ru")}
              </span>
            </button>
          ))
        ) : (
          <p className="muted small">
            Нет обращений с наступившим временем следующего контакта.
          </p>
        )}
      </div>
      {contactMore && (
        <button
          className="button secondary load-more"
          onClick={() => setContactPage((v) => v + 1)}
        >
          Загрузить ещё контакты
        </button>
      )}
      {lead && (
        <LeadEditor
          initial={lead}
          root={root}
          meta={meta}
          onClose={() => setLead(null)}
          onSaved={refresh}
          onOpenClient={onOpenClient}
        />
      )}
    </section>
  );
}
