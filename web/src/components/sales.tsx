"use client";
import { useEffect, useState } from "react";
import { ArrowRight, Plus, Search, Phone, UserRound } from "lucide-react";
import { api, errorMessage } from "@/lib/api";

import type { ClientRecord, LeadRecord, Metadata, List } from "./sales/types";
import { Dialog, ClientFields, fields } from "./sales/forms";
import { ClientEditor } from "./sales/client-editor";
import { LeadEditor } from "./sales/lead-editor";

export function Sales({
  companyId,
  view,
  initialClientId,
}: {
  companyId: string;
  view: "clients" | "leads";
  initialClientId?: string;
}) {
  const root = `organizations/${companyId}`;
  useEffect(() => {
    if (initialClientId) void openClient(initialClientId);
  }, [initialClientId]);
  const [meta, setMeta] = useState<Metadata | null>(null),
    [clients, setClients] = useState<ClientRecord[]>([]),
    [leads, setLeads] = useState<LeadRecord[]>([]);
  const [query, setQuery] = useState(""),
    [search, setSearch] = useState(""),
    [stage, setStage] = useState("");
  const [page, setPage] = useState(1),
    [total, setTotal] = useState(0),
    [more, setMore] = useState(false),
    [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [revision, setRevision] = useState(0);
  const [modal, setModal] = useState<"client" | "lead" | null>(null),
    [selectedClient, setSelectedClient] = useState<ClientRecord | null>(null),
    [selectedLead, setSelectedLead] = useState<LeadRecord | null>(null);
  const [busy, setBusy] = useState(false),
    [formError, setFormError] = useState("");
  const [suggestions, setSuggestions] = useState<ClientRecord[]>([]),
    [clientSearch, setClientSearch] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => {
      setPage(1);
      setSearch(query);
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    let active = true;
    api<Metadata>(`${root}/pipeline`)
      .then((x) => {
        if (active) setMeta(x);
      })
      .catch((e) => {
        if (active) setError(errorMessage(e));
      });
    return () => {
      active = false;
    };
  }, [root]);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ q: search, page: String(page) });
    if (view === "leads" && stage) params.set("stage", stage);
    async function loadPage() {
      try {
        let summary: {
          total: number;
          has_more: boolean;
          counts?: Record<string, number>;
        };
        if (view === "clients") {
          const result = await api<List<ClientRecord>>(
            `${root}/clients?${params}`,
          );
          if (!active) return;
          setClients((old) =>
            page === 1 ? result.items : [...old, ...result.items],
          );
          summary = result;
        } else {
          const result = await api<List<LeadRecord>>(`${root}/leads?${params}`);
          if (!active) return;
          setLeads((old) =>
            page === 1 ? result.items : [...old, ...result.items],
          );
          summary = result;
        }
        setCounts(summary.counts || {});
        setTotal(summary.total);
        setMore(summary.has_more);
      } catch (cause) {
        if (active) setError(errorMessage(cause));
      } finally {
        if (active) setLoading(false);
      }
    }
    void loadPage();
    return () => {
      active = false;
    };
  }, [root, view, search, stage, page, revision]);
  useEffect(() => {
    if (modal !== "lead") return;
    let active = true;
    const timer = setTimeout(() => {
      api<List<ClientRecord>>(
        `${root}/clients?q=${encodeURIComponent(clientSearch)}`,
      )
        .then((x) => {
          if (active) setSuggestions(x.items);
        })
        .catch((e) => {
          if (active) setFormError(errorMessage(e));
        });
    }, 200);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [root, modal, clientSearch]);
  const refresh = () => {
    setPage(1);
    setRevision((v) => v + 1);
  };
  async function mutation(work: () => Promise<unknown>) {
    setBusy(true);
    setFormError("");
    try {
      await work();
      refresh();
    } catch (e) {
      setFormError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function openClient(id: string) {
    setError("");
    try {
      setSelectedClient(await api<ClientRecord>(`${root}/clients/${id}`));
      setFormError("");
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  async function openLead(id: string) {
    setError("");
    try {
      setSelectedLead(await api<LeadRecord>(`${root}/leads/${id}`));
      setFormError("");
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  const close = () => {
    if (busy) return;
    setModal(null);
    setSelectedClient(null);
    setSelectedLead(null);
    setFormError("");
  };
  function newLead(client?: ClientRecord) {
    setSelectedClient(null);
    setModal("lead");
    setClientSearch(client?.name || "");
    setSuggestions(client ? [client] : []);
    setFormError("");
  }
  return (
    <section className="sales-workspace">
      <div className="sales-toolbar">
        <form className="sales-search" onSubmit={(e) => e.preventDefault()}>
          <Search size={17} />
          <label className="sr-only" htmlFor="sales-search">
            Поиск
          </label>
          <input
            id="sales-search"
            placeholder={
              view === "clients" ? "Имя или телефон клиента" : "Поиск обращений"
            }
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </form>
        {view === "leads" && (
          <select
            aria-label="Фильтр по этапу"
            value={stage}
            onChange={(e) => {
              setStage(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Все этапы</option>
            {meta?.stages.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        )}
        <span className="muted small">Всего: {total}</span>
        <button
          className="button primary"
          onClick={() => {
            setFormError("");
            view === "clients" ? setModal("client") : newLead();
          }}
        >
          <Plus size={16} />
          {view === "clients" ? "Добавить клиента" : "Новое обращение"}
        </button>
      </div>
      {error && (
        <div className="alert error" role="alert">
          {error}
          <button className="text-button" onClick={refresh}>
            Повторить
          </button>
        </div>
      )}
      {loading && page === 1 ? (
        <div className="loading-state">Загружаем данные…</div>
      ) : view === "clients" ? (
        <div className="card table-card">
          {clients.length ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Клиент</th>
                    <th>Телефон</th>
                    <th>Город</th>
                    <th>Карточка</th>
                  </tr>
                </thead>
                <tbody>
                  {clients.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <div className="member-cell">
                          <span className="avatar light-avatar">
                            {c.name[0]}
                          </span>
                          <strong>{c.name}</strong>
                        </div>
                      </td>
                      <td>{c.phone || "—"}</td>
                      <td>{c.city || "—"}</td>
                      <td>
                        <button
                          className="text-button"
                          onClick={() => openClient(c.id)}
                        >
                          Открыть <ArrowRight size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state compact">
              <UserRound size={30} />
              <h3>Пока нет клиентов</h3>
              <p>
                Создайте карточку клиента, затем добавьте его первое обращение.
              </p>
            </div>
          )}
        </div>
      ) : (
        <>
          <p className="small muted sales-hint">
            Откройте обращение, чтобы сменить этап, назначить следующий контакт
            или добавить комментарий.
          </p>
          <div className="pipeline-board">
            {meta?.stages
              .filter((s) => !stage || stage === s.id)
              .map((s) => (
                <section className={`pipeline-lane lane-${s.id}`} key={s.id}>
                  <header>
                    <strong>{s.name}</strong>
                    <span>{counts[s.id] || 0}</span>
                  </header>
                  <div>
                    {leads
                      .filter((l) => l.stage === s.id)
                      .map((l) => (
                        <button
                          className="lead-card"
                          key={l.id}
                          onClick={() => openLead(l.id)}
                        >
                          <span className="lead-source">
                            {l.source || "Источник не указан"}
                          </span>
                          <strong>{l.title}</strong>
                          <span>{l.client_name}</span>
                          {l.phone && (
                            <span className="lead-phone">
                              <Phone size={12} />
                              {l.phone}
                            </span>
                          )}
                          <footer>
                            <span>{l.assignee_name}</span>
                            {l.next_contact_at && (
                              <time
                                className={
                                  Date.parse(l.next_contact_at) < Date.now()
                                    ? "overdue"
                                    : ""
                                }
                              >
                                {new Date(l.next_contact_at).toLocaleString(
                                  "ru",
                                  {
                                    day: "numeric",
                                    month: "short",
                                    hour: "2-digit",
                                    minute: "2-digit",
                                  },
                                )}
                              </time>
                            )}
                          </footer>
                        </button>
                      ))}
                    {!leads.some((l) => l.stage === s.id) && (
                      <p className="lane-empty">Нет загруженных обращений</p>
                    )}
                  </div>
                </section>
              ))}
          </div>
        </>
      )}
      {more && (
        <button
          className="button secondary load-more"
          disabled={loading}
          onClick={() => setPage((p) => p + 1)}
        >
          {loading ? "Загружаем…" : "Загрузить ещё"}
        </button>
      )}
      {modal === "client" && (
        <Dialog title="Новый клиент" onClose={close}>
          {formError && (
            <div className="alert error" role="alert">
              {formError}
            </div>
          )}
          <form
            className="auth-form"
            onSubmit={(e) => {
              e.preventDefault();
              const data = fields(e.currentTarget);
              void mutation(async () => {
                const c = await api<ClientRecord>(`${root}/clients`, data);
                setModal(null);
                setSelectedClient(c);
              });
            }}
          >
            <ClientFields />
            <button className="button primary" disabled={busy}>
              Создать карточку
            </button>
          </form>
        </Dialog>
      )}
      {modal === "lead" && (
        <Dialog title="Новое обращение" onClose={close}>
          {formError && (
            <div className="alert error" role="alert">
              {formError}
            </div>
          )}
          <form
            className="auth-form"
            onSubmit={(e) => {
              e.preventDefault();
              const data = fields(e.currentTarget);
              void mutation(async () => {
                const l = await api<LeadRecord>(`${root}/leads`, data);
                setModal(null);
                await openLead(l.id);
              });
            }}
          >
            <label>
              Найти клиента
              <input
                value={clientSearch}
                onChange={(e) => setClientSearch(e.target.value)}
                placeholder="Имя или телефон"
              />
            </label>
            <label>
              Клиент
              <select
                name="client_id"
                required
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
              Если клиента ещё нет, сначала создайте карточку в разделе
              «Клиенты».
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
            <label>
              Ответственный
              <select name="assignee_id" required>
                {meta?.assignees.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Филиал
              <select name="branch_id" required>
                {meta?.branches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
            <button className="button primary" disabled={busy}>
              Создать обращение
            </button>
          </form>
        </Dialog>
      )}
      {selectedClient && (
        <ClientEditor
          initial={selectedClient}
          root={root}
          onClose={close}
          onSaved={refresh}
          onNewLead={newLead}
          onOpenLead={(id) => {
            setSelectedClient(null);
            void openLead(id);
          }}
        />
      )}
      {selectedLead && (
        <LeadEditor
          initial={selectedLead}
          root={root}
          meta={meta}
          onClose={close}
          onSaved={refresh}
          onOpenClient={(id) => {
            setSelectedLead(null);
            void openClient(id);
          }}
        />
      )}
    </section>
  );
}
