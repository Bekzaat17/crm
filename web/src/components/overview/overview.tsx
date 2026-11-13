"use client";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Building2,
  Layers3,
  ShieldCheck,
  Users,
} from "lucide-react";
import { formatShort } from "@/lib/format";
import type { AuditEvent } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { ErrorAlert } from "@/components/ui/feedback";
import { PageHeading } from "@/components/ui/page-heading";
import { useCompany } from "@/components/workspace/company-context";

type Summary = {
  clients: number;
  leads: number;
  active_leads: number;
  admitted: number;
  refused: number;
  open_tasks: number;
  overdue_tasks: number;
  contacts_due: number;
};

function SummaryMetrics() {
  const { root, base } = useCompany();
  const { data, error } = useResource<Summary>(`${root}/summary`, {
    refreshMs: 60000,
  });
  if (error)
    return <ErrorAlert message={`Не удалось обновить сводку: ${error}`} />;
  if (!data) return null;
  const metrics: [string, number][] = [
    ["Клиенты", data.clients],
    ["Обращения в работе", data.active_leads],
    ["Поступили", data.admitted],
    ["Открытые задачи", data.open_tasks],
  ];
  return (
    <>
      <div className="sales-metrics">
        {metrics.map(([label, value]) => (
          <article className="card" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </div>
      {(data.overdue_tasks > 0 || data.contacts_due > 0) && (
        <div className="reminder-banner" role="status">
          <div>
            <strong>Требуют внимания</strong>
            <p>
              Просроченные задачи: {data.overdue_tasks}. Пора связаться по
              обращениям: {data.contacts_due}.
            </p>
          </div>
          <Link className="button secondary" href={`${base}/tasks`}>
            Открыть задачи
          </Link>
        </div>
      )}
    </>
  );
}

function RecentEvents() {
  const { root, base, can } = useCompany();
  const allowed = can("view_audit");
  const { data } = useResource<{ events: AuditEvent[] }>(
    allowed ? `${root}/audit` : null,
  );
  return (
    <article className="card">
      <div className="section-title">
        <h2>Последние действия</h2>
        <Activity size={18} className="muted" />
      </div>
      {allowed ? (
        <>
          <div className="activity-list">
            {data?.events.slice(0, 4).map((e) => (
              <div className="activity-item" key={e.id}>
                <span className="activity-dot" />
                <div>
                  <strong>{e.action}</strong>
                  <p>
                    {e.actor} · {formatShort(e.created_at)}
                  </p>
                </div>
              </div>
            ))}
          </div>
          <Link className="text-button" href={`${base}/activity`}>
            Вся история <ArrowRight size={15} />
          </Link>
        </>
      ) : (
        <div className="quiet-note">
          <ShieldCheck size={26} />
          <p>
            Управление доступом и история компании доступны владельцу и
            администратору.
          </p>
        </div>
      )}
    </article>
  );
}

export function Overview() {
  const { session, organization, base, can } = useCompany();
  const first = session.user?.name.split(" ")[0];
  const stats = [
    {
      icon: Users,
      label: "Сотрудники",
      value: organization.member_count,
      caption: "С активным доступом к компании",
      href: can("manage_team") ? `${base}/team` : null,
    },
    {
      icon: Building2,
      label: "Филиалы",
      value: organization.branches.length,
      caption: organization.branches.map((b) => b.name).join(", "),
      href: can("manage_branches") ? `${base}/settings` : null,
    },
    {
      icon: Layers3,
      label: "Воронка",
      value: null,
      caption: "Обращения по этапам вашей компании",
      href: `${base}/leads`,
    },
  ];
  return (
    <>
      <PageHeading
        eyebrow={organization.name}
        title={`Здравствуйте${first ? `, ${first}` : ""}`}
        description="Сводка по обращениям, задачам и команде."
      />
      <SummaryMetrics />
      <div className="stats-grid">
        {stats.map((s) => (
          <article className="stat-card" key={s.label}>
            <span className="stat-icon">
              <s.icon size={20} />
            </span>
            <span className="stat-label">{s.label}</span>
            {s.value === null ? (
              <strong className="text-stat">Открыть</strong>
            ) : (
              <strong>{s.value}</strong>
            )}
            <span className="stat-caption">{s.caption}</span>
            {s.href && (
              <Link className="text-button" href={s.href}>
                Перейти <ArrowRight size={14} />
              </Link>
            )}
          </article>
        ))}
      </div>
      <div className="overview-grid">
        <RecentEvents />
      </div>
    </>
  );
}
