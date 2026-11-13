"use client";
import { formatDateTime } from "@/lib/format";
import type { AuditEvent } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { ErrorAlert, LoadingState } from "@/components/ui/feedback";
import { PageHeading } from "@/components/ui/page-heading";
import { useCompany } from "@/components/workspace/company-context";
import { useSection } from "@/components/workspace/shell";

export function ActivityPage() {
  const { root } = useCompany();
  const { item, eyebrow } = useSection();
  const { data, error, reload } = useResource<{ events: AuditEvent[] }>(
    `${root}/audit`,
  );
  return (
    <>
      <PageHeading
        eyebrow={eyebrow}
        title={item?.label || "История действий"}
        description={item?.description}
      />
      <ErrorAlert message={error} onRetry={reload} />
      {!data ? (
        <LoadingState />
      ) : (
        <article className="card">
          <div className="section-title">
            <h2>Управление компанией</h2>
            <span className="small muted">Время Алматы</span>
          </div>
          <div className="activity-list full-activity">
            {data.events.map((e) => (
              <div className="activity-item" key={e.id}>
                <span className="activity-dot" />
                <div>
                  <strong>{e.action}</strong>
                  <p>{e.actor}</p>
                </div>
                <time>{formatDateTime(e.created_at)}</time>
              </div>
            ))}
          </div>
        </article>
      )}
    </>
  );
}
