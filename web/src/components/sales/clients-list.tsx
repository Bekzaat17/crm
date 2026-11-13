"use client";
import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Plus, Search, UserRound } from "lucide-react";
import type { ClientRecord } from "@/lib/types";
import { usePagedList } from "@/lib/use-paged-list";
import { useUrlQuery } from "@/lib/use-url-query";
import {
  EmptyState,
  ErrorAlert,
  LoadingState,
  LoadMore,
} from "@/components/ui/feedback";
import { PageHeading } from "@/components/ui/page-heading";
import { useCompany } from "@/components/workspace/company-context";
import { useSection } from "@/components/workspace/shell";
import { NewClientDialog } from "./new-client-dialog";

export function ClientsList() {
  const { root, base } = useCompany();
  const { item, eyebrow } = useSection();
  const search = useUrlQuery("q");
  const query = search.value;
  const [creating, setCreating] = useState(false);
  const list = usePagedList<ClientRecord>(`${root}/clients`, { q: query });
  return (
    <>
      <PageHeading
        eyebrow={eyebrow}
        title={item?.label || "Клиенты"}
        description={item?.description}
        actions={
          <button className="button primary" onClick={() => setCreating(true)}>
            <Plus size={16} /> Добавить клиента
          </button>
        }
      />
      <section className="sales-workspace">
        <div className="sales-toolbar">
          <form className="sales-search" onSubmit={(e) => e.preventDefault()}>
            <Search size={17} />
            <label className="sr-only" htmlFor="client-search">
              Поиск клиентов
            </label>
            <input
              id="client-search"
              placeholder="Имя или телефон клиента"
              value={search.draft}
              onChange={(e) => search.setDraft(e.target.value)}
            />
          </form>
          <span className="muted small">Всего: {list.total}</span>
        </div>
        <ErrorAlert message={list.error} onRetry={list.reload} />
        {list.loading && list.page === 1 ? (
          <LoadingState />
        ) : (
          <div className="card table-card">
            {list.items.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Клиент</th>
                      <th>Телефон</th>
                      <th>Город</th>
                      <th>
                        <span className="sr-only">Карточка</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.items.map((c) => (
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
                          <Link
                            className="text-button"
                            href={`${base}/clients/${c.id}`}
                          >
                            Открыть <ArrowRight size={14} />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                icon={<UserRound size={30} />}
                title={query ? "Ничего не найдено" : "Пока нет клиентов"}
                text="Создайте карточку клиента, затем добавьте его первое обращение."
              />
            )}
          </div>
        )}
        <LoadMore
          visible={list.hasMore}
          loading={list.loading}
          onClick={list.loadMore}
        />
      </section>
      {creating && <NewClientDialog onClose={() => setCreating(false)} />}
    </>
  );
}
