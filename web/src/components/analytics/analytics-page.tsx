"use client";
import { useResource } from "@/lib/use-resource";
import { ErrorAlert, LoadingState } from "@/components/ui/feedback";
import { PageHeading } from "@/components/ui/page-heading";
import { useCompany } from "@/components/workspace/company-context";
import { useSection } from "@/components/workspace/shell";
import { BarList } from "./bar-list";
import { ColumnChart } from "./column-chart";
import { AnalyticsFilters, useAnalyticsFilters } from "./filters";
import { number, percent } from "./format";
import { SERIES, type Report } from "./types";

function Tiles({ totals }: { totals: Report["totals"] }) {
  const tiles: [string, string, string][] = [
    ["Обращения", number(totals.created), "Новые за период"],
    ["Поступили", number(totals.admitted), "Начали лечение"],
    ["Отказы", number(totals.refused), "Закрыты с отказом"],
    ["Конверсия", percent(totals.conversion), "Поступили ÷ обращения"],
  ];
  return (
    <div className="kpi-grid">
      {tiles.map(([label, value, hint]) => (
        <article className="card kpi" key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
          <small className="muted">{hint}</small>
        </article>
      ))}
    </div>
  );
}

function Sources({ rows }: { rows: Report["sources"] }) {
  if (!rows.length) return <p className="chart-empty muted">Нет данных.</p>;
  return (
    <table className="analytics-table">
      <thead>
        <tr>
          <th>Источник</th>
          <th className="numeric">Обращения</th>
          <th className="numeric">Поступили</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.name}>
            <td>{row.name}</td>
            <td className="numeric">{number(row.created)}</td>
            <td className="numeric">{number(row.admitted)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Team({ rows }: { rows: NonNullable<Report["team"]> }) {
  return (
    <article className="card table-card">
      <div className="section-title padded">
        <h2>Менеджеры</h2>
      </div>
      <div className="table-scroll">
        <table className="analytics-table">
          <thead>
            <tr>
              <th>Сотрудник</th>
              <th className="numeric">Обращения</th>
              <th className="numeric">Поступили</th>
              <th className="numeric">Отказы</th>
              <th className="numeric">Конверсия</th>
              <th className="numeric">Просрочено задач</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.name}</td>
                <td className="numeric">{number(row.created)}</td>
                <td className="numeric">{number(row.admitted)}</td>
                <td className="numeric">{number(row.refused)}</td>
                <td className="numeric">{percent(row.conversion)}</td>
                <td className="numeric">{number(row.overdue_tasks)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}

export function AnalyticsPage() {
  const { root } = useCompany();
  const { item, eyebrow } = useSection();
  const filters = useAnalyticsFilters();
  const { data, error, loading, reload } = useResource<Report>(
    `${root}/analytics?${filters.query}`,
  );
  return (
    <>
      <PageHeading
        eyebrow={eyebrow}
        title={item?.label || "Аналитика"}
        description={
          data?.scope === "own"
            ? "Ваши обращения и поступления за период."
            : item?.description
        }
      />
      <AnalyticsFilters filters={filters} assignees={data?.assignees || []} />
      <ErrorAlert message={error} onRetry={reload} />
      {!data ? (
        loading && <LoadingState />
      ) : (
        <div className={`analytics ${loading ? "is-refreshing" : ""}`}>
          <Tiles totals={data.totals} />
          <article className="card chart-card">
            <div className="section-title">
              <h2>Обращения и поступления</h2>
              <ul className="chart-legend">
                {SERIES.map((s) => (
                  <li key={s.key}>
                    <i style={{ background: s.color }} aria-hidden />
                    {s.label}
                  </li>
                ))}
              </ul>
            </div>
            <ColumnChart points={data.series} bucket={data.period.bucket} />
          </article>
          <div className="analytics-grid">
            <article className="card chart-card">
              <div className="section-title">
                <h2>Откуда приходят</h2>
              </div>
              <Sources rows={data.sources} />
            </article>
            <article className="card chart-card">
              <div className="section-title">
                <h2>Почему отказываются</h2>
              </div>
              <BarList
                label="Причины отказов"
                color="var(--series-refused)"
                rows={data.refusal_reasons.map((r) => ({
                  key: r.reason,
                  label: r.reason,
                  value: r.count,
                }))}
                empty="Отказов за период нет."
              />
            </article>
          </div>
          {data.team && <Team rows={data.team} />}
        </div>
      )}
    </>
  );
}
