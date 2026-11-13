"use client";
import { useState } from "react";
import Link from "next/link";
import { Plus, Search, Settings2 } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import type { LeadRecord, PipelineMeta, Stage } from "@/lib/types";
import { usePagedList } from "@/lib/use-paged-list";
import { useResource } from "@/lib/use-resource";
import { useUrlQuery } from "@/lib/use-url-query";
import { ErrorAlert, LoadingState, LoadMore } from "@/components/ui/feedback";
import { PageHeading } from "@/components/ui/page-heading";
import { useCompany } from "@/components/workspace/company-context";
import { useSection } from "@/components/workspace/shell";
import { LeadCard } from "./lead-card";
import { NewLeadDialog } from "./new-lead-dialog";
import { RefusalDialog } from "./refusal-dialog";

type PendingMove = { lead: LeadRecord; stage: Stage };

export function LeadsBoard() {
  const { root, base } = useCompany();
  const { item, eyebrow } = useSection();
  const meta = useResource<PipelineMeta>(`${root}/pipeline`);
  const search = useUrlQuery("q");
  const stageFilter = useUrlQuery("stage");
  const list = usePagedList<LeadRecord>(`${root}/leads`, {
    q: search.value,
    stage: stageFilter.value,
  });
  const [creating, setCreating] = useState(false);
  const [refusal, setRefusal] = useState<PendingMove | null>(null);
  const [moving, setMoving] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const [moveError, setMoveError] = useState("");
  const stages = (meta.data?.stages || []).filter(
    (s) => !stageFilter.value || s.id === stageFilter.value,
  );

  async function move(lead: LeadRecord, stage: Stage, reason?: string) {
    setMoveError("");
    setMoving(lead.id);
    // Оптимистично переносим одну карточку; откатываем тоже только её, чтобы
    // не потерять страницы, догруженные во время запроса.
    const place = (stageId: string) =>
      list.setItems((items) =>
        items.map((l) => (l.id === lead.id ? { ...l, stage: stageId } : l)),
      );
    place(stage.id);
    list.adjustCounts({ [lead.stage]: -1, [stage.id]: 1 });
    try {
      const saved = await api<LeadRecord>(`${root}/leads/${lead.id}`, {
        stage: stage.id,
        version: lead.version,
        ...(reason ? { refusal_reason: reason } : {}),
      });
      list.setItems((items) =>
        items.map((l) => (l.id === saved.id ? saved : l)),
      );
    } catch (cause) {
      place(lead.stage);
      list.adjustCounts({ [lead.stage]: 1, [stage.id]: -1 });
      setMoveError(errorMessage(cause));
    } finally {
      setMoving(null);
    }
  }

  function drop(stage: Stage, leadId: string) {
    setDropTarget(null);
    const lead = list.items.find((l) => l.id === leadId);
    if (!lead || lead.stage === stage.id || moving) return;
    if (stage.kind === "refused") setRefusal({ lead, stage });
    else void move(lead, stage);
  }

  return (
    <>
      <PageHeading
        eyebrow={eyebrow}
        title={item?.label || "Воронка"}
        description={item?.description}
        actions={
          <>
            {meta.data?.can_manage_pipeline && (
              <Link
                className="button secondary"
                href={`${base}/settings/pipeline`}
              >
                <Settings2 size={16} /> Этапы
              </Link>
            )}
            <button
              className="button primary"
              disabled={!meta.data}
              onClick={() => setCreating(true)}
            >
              <Plus size={16} /> Новое обращение
            </button>
          </>
        }
      />
      <section className="sales-workspace">
        <div className="sales-toolbar">
          <form className="sales-search" onSubmit={(e) => e.preventDefault()}>
            <Search size={17} />
            <label className="sr-only" htmlFor="lead-search">
              Поиск обращений
            </label>
            <input
              id="lead-search"
              placeholder="Название, клиент или телефон"
              value={search.draft}
              onChange={(e) => search.setDraft(e.target.value)}
            />
          </form>
          <select
            aria-label="Фильтр по этапу"
            value={stageFilter.value}
            onChange={(e) => stageFilter.set(e.target.value)}
          >
            <option value="">Все этапы</option>
            {meta.data?.stages.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <span className="muted small">Всего: {list.total}</span>
        </div>
        <ErrorAlert
          message={meta.error || list.error}
          onRetry={() => {
            if (meta.error) meta.reload();
            if (list.error) list.reload();
          }}
        />
        <ErrorAlert message={moveError} />
        {(list.loading && list.page === 1) || !meta.data ? (
          <LoadingState />
        ) : (
          <div className="pipeline-board">
            {stages.map((stage) => {
              const leads = list.items.filter((l) => l.stage === stage.id);
              return (
                <section
                  key={stage.id}
                  className={`pipeline-lane lane-${stage.kind} ${dropTarget === stage.id ? "lane-drop" : ""}`}
                  style={
                    stage.color ? { borderTopColor: stage.color } : undefined
                  }
                  aria-label={stage.name}
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "move";
                    setDropTarget(stage.id);
                  }}
                  onDragLeave={() => setDropTarget(null)}
                  onDrop={(e) => {
                    e.preventDefault();
                    drop(stage, e.dataTransfer.getData("text/lead-id"));
                  }}
                >
                  <header>
                    <strong>{stage.name}</strong>
                    <span>{list.counts[stage.id] || 0}</span>
                  </header>
                  <div>
                    {leads.map((lead) => (
                      <LeadCard
                        key={lead.id}
                        lead={lead}
                        href={`${base}/leads/${lead.id}`}
                        pending={moving === lead.id}
                      />
                    ))}
                    {!leads.length && (
                      <p className="lane-empty">
                        Перетащите сюда карточку обращения
                      </p>
                    )}
                  </div>
                </section>
              );
            })}
          </div>
        )}
        <LoadMore
          visible={list.hasMore}
          loading={list.loading}
          onClick={list.loadMore}
        />
      </section>
      {creating && meta.data && (
        <NewLeadDialog meta={meta.data} onClose={() => setCreating(false)} />
      )}
      {refusal && (
        <RefusalDialog
          stageName={refusal.stage.name}
          onClose={() => setRefusal(null)}
          onConfirm={(reason) => {
            setRefusal(null);
            void move(refusal.lead, refusal.stage, reason);
          }}
        />
      )}
    </>
  );
}
